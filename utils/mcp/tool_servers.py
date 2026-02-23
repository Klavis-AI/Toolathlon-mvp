"""
Drop-in replacement for Toolathlon/utils/mcp/tool_servers.py.

Instead of reading YAML config files and spawning local stdio/sse servers,
this module reads Klavis MCP server URLs from the KLAVIS_MCP_SERVER_URLS
environment variable and connects via Streamable HTTP (the transport used
by all Klavis sandbox MCP servers).

Env var format (set by toolathlon_task_run_example.py before running
preprocess/evaluation subprocesses):

    KLAVIS_MCP_SERVER_URLS = '{"google_calendar": {"url": "https://...", "headers": {}}, ...}'

The public API is identical to the original:
    - MCPServerManager(agent_workspace, config_dir=..., debug=..., local_token_key_session=...)
    - MCPServerManager.servers                 -> Dict[str, server]
    - MCPServerManager.connected_servers       -> Dict[str, server]
    - MCPServerManager.connect_servers(names)
    - MCPServerManager.disconnect_servers(names)
    - MCPServerManager.is_server_connected(name)
    - MCPServerManager.get_connected_server_names()
    - MCPServerManager.get_all_connected_servers()
    - MCPServerManager.get_available_servers()
    - async with manager: ...
    - async with manager.servers['name'] as s: ...
    - call_tool_with_retry(server, tool_name, arguments)
    - ToolCallError
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any

from agents.mcp import MCPServerStreamableHttp


# ─── ToolCallError ───────────────────────────────────────────────────────────

class ToolCallError(Exception):
    """Custom exception type for tool call errors (same as original)."""

    def __init__(self, message: str, original_exception: Exception = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(self.message)


# ─── MCPServerManager ────────────────────────────────────────────────────────

class MCPServerManager:
    """
    Klavis-backed replacement for the original MCPServerManager.

    Reads server URLs from the KLAVIS_MCP_SERVER_URLS env var and wraps each
    in an MCPServerStreamableHttp instance.  The constructor signature accepts
    the same kwargs as the original (agent_workspace, config_dir, debug,
    local_token_key_session) so that task code doesn't need any changes;
    config_dir and local_token_key_session are simply ignored since all
    server config comes from the env var.
    """

    def __init__(
        self,
        agent_workspace: str = "./",
        config_dir: str = "configs/mcp_servers",  # ignored — kept for API compat
        debug: bool = False,
        local_token_key_session: Dict = None,       # ignored — kept for API compat
    ):
        self.agent_workspace = os.path.abspath(agent_workspace)
        self.debug = debug
        self.servers: Dict[str, MCPServerStreamableHttp] = {}
        self.connected_servers: Dict[str, MCPServerStreamableHttp] = {}
        # Track async context managers for servers connected via connect_servers()
        self._active_cms: Dict[str, Any] = {}

        # Parse server URLs from env
        raw = os.environ.get("KLAVIS_MCP_SERVER_URLS", "{}")
        try:
            server_map: Dict[str, dict] = json.loads(raw)
        except json.JSONDecodeError:
            server_map = {}

        if debug and server_map:
            print(f"[MCPServerManager] Loading {len(server_map)} Klavis servers from env")

        for name, info in server_map.items():
            url = info.get("url", "") if isinstance(info, dict) else str(info)
            headers = info.get("headers", {}) if isinstance(info, dict) else {}
            if not url:
                continue
            params: dict = {"url": url}
            if headers:
                params["headers"] = headers
            server = MCPServerStreamableHttp(
                params=params,
                name=name,
                cache_tools_list=True,
                client_session_timeout_seconds=120,
            )
            self.servers[name] = server
            if debug:
                print(f"  - Registered server: {name} -> {url}")

    # ── Connection management ────────────────────────────────────────────

    async def connect_servers(
        self,
        server_names: Optional[List[str]] = None,
        max_connect_retries: int = 3,
        connect_retry_delay: float = 2.0,
    ):
        """Connect named servers (enter their async context managers)."""
        if server_names is None:
            server_names = list(self.servers.keys())

        for name in server_names:
            if name not in self.servers:
                print(f"Warning: Server '{name}' not found in KLAVIS_MCP_SERVER_URLS")
                continue
            if name in self.connected_servers:
                if self.debug:
                    print(f"  Server '{name}' already connected, skipping")
                continue

            server = self.servers[name]
            last_err = None
            for attempt in range(max_connect_retries + 1):
                try:
                    cm = server.__aenter__()
                    await cm
                    self._active_cms[name] = server
                    self.connected_servers[name] = server
                    if self.debug:
                        print(f"  - Connected: {name} (attempt {attempt + 1})")
                    break
                except Exception as e:
                    last_err = e
                    if attempt < max_connect_retries:
                        if self.debug:
                            print(f"  Connection failed for {name} (attempt {attempt + 1}): {e}")
                        await asyncio.sleep(connect_retry_delay)
                    else:
                        print(f"Failed to connect server '{name}' after {max_connect_retries + 1} attempts: {e}")

    async def disconnect_servers(
        self,
        server_names: Optional[List[str]] = None,
        max_disconnect_retries: int = 3,
        disconnect_retry_delay: float = 1.0,
    ):
        """Disconnect named servers (exit their async context managers)."""
        if server_names is None:
            server_names = list(self._active_cms.keys())

        for name in list(server_names):
            server = self._active_cms.pop(name, None)
            self.connected_servers.pop(name, None)
            if server is not None:
                try:
                    await server.__aexit__(None, None, None)
                    if self.debug:
                        print(f"  - Disconnected: {name}")
                except Exception as e:
                    if self.debug:
                        print(f"  - Error disconnecting {name}: {e}")

    async def ensure_all_disconnected(self, **kwargs):
        """Disconnect every server that was connected via connect_servers()."""
        await self.disconnect_servers()

    # ── Query helpers ────────────────────────────────────────────────────

    def is_server_connected(self, server_name: str) -> bool:
        return server_name in self.connected_servers

    def get_connected_server_names(self) -> List[str]:
        return list(self.connected_servers.keys())

    def get_all_connected_servers(self) -> list:
        return list(self.connected_servers.values())

    def get_available_servers(self) -> List[str]:
        return list(self.servers.keys())

    # ── Async context manager (for `async with MCPServerManager(...):`) ──

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.ensure_all_disconnected()


# ─── call_tool_with_retry ────────────────────────────────────────────────────

async def call_tool_with_retry(
    server,
    tool_name: str,
    arguments: dict,
    retry_time: int = 5,
    delay: float = 1.0,
):
    """
    Call a tool on an MCP server with automatic retries.

    Args:
        server:     MCP server instance (MCPServerStreamableHttp)
        tool_name:  Name of the tool to invoke
        arguments:  Dict of arguments for the tool
        retry_time: Max number of retries (default 5)
        delay:      Seconds between retries (default 1)

    Returns:
        CallToolResult from the MCP server

    Raises:
        ToolCallError: If all attempts fail
    """
    last_exception = None
    for attempt in range(retry_time + 1):
        try:
            result = await server.call_tool(tool_name=tool_name, arguments=arguments)
            return result
        except Exception as e:
            last_exception = e
            if attempt < retry_time:
                print(f"Tool call failed (attempt {attempt + 1}/{retry_time + 1}): {e}")
                print(f"Waiting {delay} seconds to retry...")
                await asyncio.sleep(delay)
            else:
                print(f"Tool call failed (attempt {retry_time + 1} times): {e}")

    raise ToolCallError(f"Tool call failed: {tool_name}", last_exception)
