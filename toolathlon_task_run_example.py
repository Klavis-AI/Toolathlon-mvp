"""
Toolathlon task runner using Klavis Sandbox + OpenAI Agents SDK.

Usage:
    export KLAVIS_API_KEY=...
    export ANTHROPIC_API_KEY=...
    export OPENAI_API_KEY=...
    python toolathlon_task_run_example.py --task [task_name]
"""

import asyncio
import base64
import io
import json
import logging
import os
import signal
import sys
import shutil
import subprocess
import tempfile
import tarfile
import importlib.util
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, List

import httpx
from dotenv import load_dotenv
from agents import Agent, Runner, RunHooks, ModelSettings
from agents.mcp import MCPServerManager, MCPServerStreamableHttp

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

logging.getLogger("openai.agents").setLevel(logging.CRITICAL) # Suppress OpenAI Agents SDK logging, this is non-fatal.

# Local tools copied from Toolathlon/utils/aux_tools/ (mirrored structure), they are needed for the task to run.
# "python_execute" is intentionally excluded (runs on Klavis sandbox instead).
from utils.aux_tools.basic import tool_sleep, tool_done
from utils.aux_tools.context_management_tools import context_management_tools
from utils.aux_tools.history_tools import history_tools
from utils.aux_tools.overlong_tool_manager import overlong_tool_tools
from utils.aux_tools.web_search import tool_web_search

LOCAL_TOOL_MAPPINGS = {
    "sleep": tool_sleep,
    "claim_done": tool_done,
    "manage_context": context_management_tools,
    "history": history_tools,
    "handle_overlong_tool_outputs": overlong_tool_tools,
    "web_search": tool_web_search,
}

TASKS_DIR = PROJECT_ROOT
OUTPUT_DIR = PROJECT_ROOT
DEFAULT_MODEL = "litellm/anthropic/claude-sonnet-4-6"

def _ansi(code: str) -> str:
    return code if sys.stdout.isatty() else ""

_GREEN = _ansi("\033[92m")
_CYAN = _ansi("\033[96m")
_YELLOW = _ansi("\033[93m")
_RED = _ansi("\033[91m")
_BLUE = _ansi("\033[94m")
_DIM = _ansi("\033[2m")
_RST = _ansi("\033[0m")

KLAVIS_API_BASE = "https://api.klavis.ai"

# ========================== Tool Call Logging Hooks ==========================

class ToolLoggingHooks(RunHooks):
    """RunHooks subclass that prints every tool call request and response in real time."""

    async def on_tool_end(self, context, agent, tool, result) -> None:
        result_str = str(result)
        truncated = result_str[:1000] + (" …(truncated)" if len(result_str) > 1000 else "")
        print(f"{_GREEN}[tool result]{_RST} {_YELLOW}{tool.name}{_RST}")
        print(f"  {_DIM}{truncated}{_RST}")

    async def on_llm_end(self, context, agent, response) -> None:
        """Print tool call arguments from the LLM response as soon as they arrive."""
        for output in response.output:
            name = getattr(output, 'name', None)
            arguments = getattr(output, 'arguments', None)
            if name and arguments is not None:
                args_str = str(arguments)
                truncated_args = args_str[:500] + (' …' if len(args_str) > 500 else '')
                print(f"{_CYAN}[tool request]{_RST} {_YELLOW}{name}{_RST}")
                print(f"  {_DIM}arguments: {truncated_args}{_RST}")


LOCAL_SANDBOX_SERVERS = {
    "filesystem", "git", "terminal", "desktop-commander",
    "arxiv", "excel", "word", "powerpoint",
    "code-executor", "code-runner", "pdf-tools",
    "google_cloud", "poste_email_toolathlon", "localmemory",
}

TASK_TO_LOCAL_SANDBOX_NAME = {
    "python_execute": "code-executor",
    "pptx": "powerpoint",
    "arxiv_local": "arxiv",
    "emails": "poste_email_toolathlon",
    "memory": "localmemory",
    "google-cloud": "google_cloud",
}

TASK_SERVER_TO_SANDBOX_NAME = {
    "arxiv-latex": "arxiv_latex",
    "google_sheet": "google_sheets",
    "wandb": "weights_and_biases",
}

# Task-level token_key_session.py must use os.environ.get("KLAVIS_*") to pick up
# these credentials, since the MVP runner injects them as env vars, not via file rewriting.
SANDBOX_AUTH_ENV_MAPPING = {
    "woocommerce": {
        "consumer_key": "KLAVIS_WOOCOMMERCE_CONSUMER_KEY",
        "consumer_secret": "KLAVIS_WOOCOMMERCE_CONSUMER_SECRET",
        "site_url": "KLAVIS_WOOCOMMERCE_SITE_URL",
        "admin_username": "KLAVIS_WOOCOMMERCE_ADMIN_USERNAME",
        "admin_password": "KLAVIS_WOOCOMMERCE_ADMIN_PASSWORD",
    },
    "github": {
        "access_token": "KLAVIS_GITHUB_TOKEN",
    },
    "huggingface": {
        "access_token": "KLAVIS_HUGGINGFACE_TOKEN",
    },
    "snowflake": {
        "SNOWFLAKE_ACCOUNT": "KLAVIS_SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_WAREHOUSE": "KLAVIS_SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_ROLE": "KLAVIS_SNOWFLAKE_ROLE",
        "SNOWFLAKE_USER": "KLAVIS_SNOWFLAKE_USER",
        "SNOWFLAKE_PRIVATE_KEY": "KLAVIS_SNOWFLAKE_PRIVATE_KEY",
        "SNOWFLAKE_DATABASE": "KLAVIS_SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA": "KLAVIS_SNOWFLAKE_SCHEMA",
    },
    "notion": {
        "toolathon_notion_integration_key": "KLAVIS_NOTION_INTEGRATION_KEY",
        "toolathon_notion_integration_key_eval": "KLAVIS_NOTION_INTEGRATION_KEY_EVAL",
        "toolathon_source_notion_page_url": "KLAVIS_SOURCE_NOTION_PAGE_URL",
        "toolathon_eval_notion_page_url": "KLAVIS_EVAL_NOTION_PAGE_URL",
    },
}

# Servers whose auth_data contains Google OAuth credentials (token,
# refresh_token, client_id, client_secret, scopes).  We write these to a temp
# file and monkeypatch open() via HIJACK_GOOGLE_CREDENTIALS_PATH so that child
# processes reading configs/google_credentials.json get the sandbox credentials.
GOOGLE_CREDENTIALS_SERVERS = {"google_sheets", "google_forms"}
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

# Servers whose auth_data contains a GCP service-account JSON key.
# We write the key to a temp file and set HIJACK_GCP_SERVICE_ACCOUNT_PATH
# so that child processes reading configs/gcp-service_account.keys.json
# get the sandbox credentials via the file-open hijack.
GCP_CREDENTIALS_SERVERS = {"google_cloud"}


# ========================== Klavis Sandbox Client ==========================

class KlavisSandbox:
    """Klavis MCP Sandbox API client."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("KLAVIS_API_KEY")
        if not self.api_key:
            raise ValueError("KLAVIS_API_KEY is required")
        self.acquired_sandboxes: List[Dict] = []
        self.local_sandbox_id: Optional[str] = None
        self.auth_env: Dict[str, str] = {}
        self._google_creds_temp_file: Optional[str] = None
        self._snowflake_key_temp_file: Optional[str] = None
        self._gcp_sa_temp_file: Optional[str] = None

    @staticmethod
    def _to_local_sandbox_name(task_name: str) -> str:
        return TASK_TO_LOCAL_SANDBOX_NAME.get(task_name, task_name)

    @staticmethod
    def _is_local_sandbox_server(task_name: str) -> bool:
        return KlavisSandbox._to_local_sandbox_name(task_name) in LOCAL_SANDBOX_SERVERS

    def get_local_sandbox_id(self) -> Optional[str]:
        """Return the local_sandbox_id if a local sandbox was acquired."""
        return self.local_sandbox_id

    def acquire(self, server_name: str, extra_params: Optional[Dict] = None) -> Optional[Dict]:
        """Acquire an individual sandbox for a non-local-sandbox server."""
        url = f"{KLAVIS_API_BASE}/sandbox/{server_name}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {"benchmark": "Toolathlon"}
        if extra_params:
            body.update(extra_params)
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            self.acquired_sandboxes.append(data)
            return data
        except Exception as e:
            print(f"[Klavis] Failed to acquire sandbox for '{server_name}': {e}")
            return None

    def acquire_local_sandbox(self, server_names: List[str]) -> Optional[Dict]:
        """Acquire a local sandbox with multiple MCP servers via POST /local-sandbox."""
        url = f"{KLAVIS_API_BASE}/local-sandbox"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "server_names": server_names,
            "benchmark": "Toolathlon",
        }
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            self.local_sandbox_id = data.get("local_sandbox_id")
            return data
        except Exception as e:
            print(f"[Klavis] Failed to acquire local sandbox: {e}")
            return None

    def acquire_for_servers(self, server_names: List[str], server_extra_params: Optional[Dict[str, Dict]] = None) -> Dict[str, str]:
        """Acquire sandboxes for multiple servers.

        Servers matching LocalSandboxMCPServer are grouped into a single
        POST /local-sandbox call. Others use individual sandbox endpoints.
        """
        if server_extra_params is None:
            server_extra_params = {}
        overrides = {}

        local_requested = [n for n in server_names if self._is_local_sandbox_server(n)]
        other_servers = [n for n in server_names if not self._is_local_sandbox_server(n)]

        if local_requested:
            remote_names = [self._to_local_sandbox_name(n) for n in local_requested]
            result = self.acquire_local_sandbox(remote_names)
            if result and result.get("servers"):
                remote_to_task = {self._to_local_sandbox_name(n): n for n in local_requested}
                for server in result["servers"]:
                    sname = server.get("server_name")
                    surl = server.get("mcp_server_url")
                    if sname and surl:
                        task_name = remote_to_task.get(sname, sname)
                        overrides[task_name] = surl
                        print(f"[Klavis] Acquired local sandbox server '{task_name}' (remote '{sname}'): {surl}")
                    # Extract email server auth_data for socket hijacking.
                    # Child scripts hardcode localhost:1143/1587 for IMAP/SMTP.
                    # We store the real remote IP:port as HIJACK_* env vars so
                    # that _hijack/sitecustomize.py can redirect them.
                    if sname == "poste_email_toolathlon":
                        auth = server.get("auth_data") or {}
                        if auth.get("imap_server"):
                            self.auth_env["HIJACK_IMAP_HOST"] = str(auth["imap_server"])
                            self.auth_env["HIJACK_IMAP_PORT"] = str(auth.get("imap_port", 1143))
                            print(f"[Klavis] Email hijack: IMAP -> {auth['imap_server']}:{auth.get('imap_port', 1143)}")
                        if auth.get("smtp_server"):
                            self.auth_env["HIJACK_SMTP_HOST"] = str(auth["smtp_server"])
                            self.auth_env["HIJACK_SMTP_PORT"] = str(auth.get("smtp_port", 1587))
                            print(f"[Klavis] Email hijack: SMTP -> {auth['smtp_server']}:{auth.get('smtp_port', 1587)}")
                    # Extract GCP service-account auth_data for file-open hijacking.
                    # Child preprocess/eval scripts open configs/gcp-service_account.keys.json;
                    # we write the real credentials to a temp file and redirect via HIJACK_*.
                    if sname in GCP_CREDENTIALS_SERVERS:
                        auth = server.get("auth_data") or {}
                        if auth:
                            self._apply_gcp_credentials_from_auth(auth)

        for name in other_servers:
            sandbox_name = TASK_SERVER_TO_SANDBOX_NAME.get(name, name)
            result = self.acquire(sandbox_name, extra_params=server_extra_params.get(name))
            if result and result.get("server_urls"):
                for sname, surl in result["server_urls"].items():
                    key = name if sname == sandbox_name else sname
                    overrides[key] = surl
                    print(f"[Klavis] Acquired sandbox for '{key}': {surl}")
                sandbox_id = result.get("sandbox_id")
                if sandbox_id:
                    self._apply_sandbox_auth(sandbox_name, sandbox_id)
                    # For Google OAuth servers, write auth_data to a temp file
                    # and set HIJACK_GOOGLE_CREDENTIALS_PATH so that child
                    # processes reading configs/google_credentials.json get the
                    # sandbox credentials instead.
                    if sandbox_name == "snowflake":
                        self._apply_snowflake_private_key()
                    if sandbox_name in GOOGLE_CREDENTIALS_SERVERS:
                        self._apply_google_credentials(sandbox_name, sandbox_id)
        return overrides

    def _apply_sandbox_auth(self, server_name: str, sandbox_id: str):
        """Fetch auth_data/metadata from Klavis sandbox and store in self.auth_env.

        Most servers store credentials in auth_data; Notion has extra metadata.
        We check both so a single SANDBOX_AUTH_ENV_MAPPING works for either case.
        """
        mapping = SANDBOX_AUTH_ENV_MAPPING.get(server_name)
        if not mapping:
            return
        details = self.get_sandbox_details(server_name, sandbox_id) or {}
        auth = details.get("auth_data") or {}
        meta = details.get("metadata") or {}
        for key, env_var in mapping.items():
            val = auth.get(key) if auth.get(key) is not None else meta.get(key)
            if val is not None:
                self.auth_env[env_var] = str(val)
                print(f"[Klavis] Set {env_var}")

        if server_name == "notion":
            ## set the notion official mcp access token, because Toolathlon preprocess scripts need use the official notion mcp to duplicate pages
            for source in [auth, meta, details]:
                mcp_auth = source.get("mcp_auth_data")
                if isinstance(mcp_auth, dict):
                    notion_official_access_token = (mcp_auth.get("token") or {}).get("access_token")
                    if notion_official_access_token:
                        self.auth_env["KLAVIS_NOTION_OFFICIAL_MCP_ACCESS_TOKEN"] = notion_official_access_token
                        print(f"[Klavis] Set KLAVIS_NOTION_OFFICIAL_MCP_ACCESS_TOKEN")
                        break

    def _apply_snowflake_private_key(self):
        """Write SNOWFLAKE_PRIVATE_KEY to a temp file and set the PATH env var."""
        pk = self.auth_env.get("KLAVIS_SNOWFLAKE_PRIVATE_KEY")
        if not pk:
            return
        tf = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".pem", prefix="snowflake_pk_",
        )
        try:
            tf.write(pk)
            tf.close()
            self._snowflake_key_temp_file = tf.name
            self.auth_env["KLAVIS_SNOWFLAKE_PRIVATE_KEY_PATH"] = tf.name
            print(f"[Klavis] Snowflake private key written to temp file: {tf.name}")
        except Exception as e:
            tf.close()
            os.unlink(tf.name)
            print(f"[Klavis] Failed to write Snowflake private key temp file: {e}")

    def _apply_google_credentials(self, server_name: str, sandbox_id: str):
        """Write Google OAuth auth_data to a temp file for file-open hijacking.

        The auth_data returned by Klavis for google_sheets / google_forms
        contains token, refresh_token, client_id, client_secret, and scopes.
        We add the constant token_uri and write the full JSON to a temp file.
        HIJACK_GOOGLE_CREDENTIALS_PATH is set so that _hijack/
        sitecustomize.py can redirect any open("configs/google_credentials.json")
        to this temp file.
        """
        details = self.get_sandbox_details(server_name, sandbox_id)
        auth = (details or {}).get("auth_data")
        if not auth:
            print(f"[Klavis] No auth_data for '{server_name}' — skipping Google credentials hijack")
            return

        # Add the constant token_uri that Klavis doesn't include
        creds = dict(auth)
        creds.setdefault("token_uri", GOOGLE_TOKEN_URI)
        creds.setdefault("token", creds.get("access_token", ""))
        creds.setdefault("scopes", creds.get("scope", "").split(" "))

        # Write to a dedicated temp file (delete=False so the child can read it)
        tf = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", prefix="google_creds_",
        )
        try:
            json.dump(creds, tf, indent=2)
            tf.close()
            self._google_creds_temp_file = tf.name
            self.auth_env["HIJACK_GOOGLE_CREDENTIALS_PATH"] = tf.name
            print(f"[Klavis] Google credentials written to temp file: {tf.name}")
        except Exception as e:
            tf.close()
            os.unlink(tf.name)
            print(f"[Klavis] Failed to write Google credentials temp file: {e}")

    def _apply_gcp_credentials_from_auth(self, auth: Dict):
        """Write GCP service-account auth_data to a temp file for file-open hijacking.

        The auth_data returned by the Klavis google_cloud sandbox contains
        the full GCP service-account JSON key.  We write it to a temp file
        and set HIJACK_GCP_SERVICE_ACCOUNT_PATH so that _hijack/
        sitecustomize.py redirects any open("configs/gcp-service_account.keys.json")
        to this temp file.
        """
        tf = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", prefix="gcp_sa_",
        )
        try:
            json.dump(auth, tf, indent=2)
            tf.close()
            self._gcp_sa_temp_file = tf.name
            self.auth_env["HIJACK_GCP_SERVICE_ACCOUNT_PATH"] = tf.name
            print(f"[Klavis] GCP service-account credentials written to temp file: {tf.name}")
        except Exception as e:
            tf.close()
            os.unlink(tf.name)
            print(f"[Klavis] Failed to write GCP service-account temp file: {e}")

    def cleanup_temp_files(self):
        """Remove any temporary files created for credential hijacking."""
        for attr, label in [
            ("_google_creds_temp_file", "Google credentials"),
            ("_snowflake_key_temp_file", "Snowflake private key"),
            ("_gcp_sa_temp_file", "GCP service-account"),
        ]:
            path = getattr(self, attr, None)
            if path:
                try:
                    os.unlink(path)
                    print(f"[Klavis] Removed temp {label}: {path}")
                except OSError:
                    pass
                setattr(self, attr, None)

    def get_sandbox_details(self, server_name: str, sandbox_id: str) -> Optional[Dict]:
        """Get detailed information about a specific sandbox instance."""
        url = f"{KLAVIS_API_BASE}/sandbox/{server_name}/{sandbox_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Klavis] Failed to get sandbox details for '{sandbox_id}': {e}")
            return None

    def release_all(self):
        """Release all acquired sandboxes."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if self.local_sandbox_id:
            try:
                resp = httpx.delete(
                    f"{KLAVIS_API_BASE}/local-sandbox/{self.local_sandbox_id}",
                    headers=headers, timeout=30,
                )
                resp.raise_for_status()
                print(f"[Klavis] Released local sandbox '{self.local_sandbox_id}'")
            except Exception as e:
                print(f"[Klavis] Failed to release local sandbox '{self.local_sandbox_id}': {e}")
            self.local_sandbox_id = None
        for sandbox in self.acquired_sandboxes:
            sandbox_id = sandbox.get("sandbox_id")
            server_name = sandbox.get("server_name")
            if not sandbox_id or not server_name:
                continue
            try:
                resp = httpx.delete(
                    f"{KLAVIS_API_BASE}/sandbox/{server_name}/{sandbox_id}",
                    headers=headers, timeout=30,
                )
                resp.raise_for_status()
                print(f"[Klavis] Released sandbox '{sandbox_id}' for '{server_name}'")
            except Exception as e:
                print(f"[Klavis] Failed to release sandbox '{sandbox_id}': {e}")
        self.acquired_sandboxes.clear()

    def get_upload_url(self, local_sandbox_id: str) -> Optional[Dict]:
        """Get a signed URL to upload a tar.gz archive to a local sandbox."""
        url = f"{KLAVIS_API_BASE}/local-sandbox/{local_sandbox_id}/upload-url"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = httpx.post(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Klavis] Failed to get upload URL for '{local_sandbox_id}': {e}")
            return None

    def move_files_to_workspace(self, local_sandbox_id: str) -> Optional[Dict]:
        """Extract the uploaded tar.gz archive into the sandbox workspace."""
        url = f"{KLAVIS_API_BASE}/local-sandbox/{local_sandbox_id}/initialize"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = httpx.post(url, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Klavis] Failed to initialize sandbox '{local_sandbox_id}': {e}")
            return None

    def get_workspace_download_url(self, local_sandbox_id: str) -> Optional[Dict]:
        """Get a signed URL to download the sandbox workspace as a tar.gz archive."""
        url = f"{KLAVIS_API_BASE}/local-sandbox/{local_sandbox_id}/dump"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=300)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Klavis] Failed to dump sandbox '{local_sandbox_id}': {e}")
            return None

# ========================== Workspace Helpers ==========================

def upload_workspace_tarball(klavis: KlavisSandbox, tarball_path: str, timeout: int = 120) -> Optional[Dict]:
    """Upload a tar.gz file to the local sandbox and extract it."""
    sandbox_id = klavis.local_sandbox_id
    if not sandbox_id:
        print("[Klavis] No local sandbox acquired — cannot upload")
        return None

    with open(tarball_path, "rb") as f:
        content = f.read()
    if not content:
        print("[Klavis] Tarball is empty — skipping upload")
        return None

    upload_resp = klavis.get_upload_url(sandbox_id)
    if not upload_resp or "upload_url" not in upload_resp:
        return None

    resp = httpx.put(
        upload_resp["upload_url"],
        headers={"Content-Type": "application/gzip"},
        content=content,
        timeout=timeout,
    )
    resp.raise_for_status()

    return klavis.move_files_to_workspace(sandbox_id)


def download_workspace(klavis: KlavisSandbox, directory: str, timeout: int = 120) -> None:
    """Download the workspace from the local sandbox into *directory*."""
    sandbox_id = klavis.local_sandbox_id
    if not sandbox_id:
        print("[Klavis] No local sandbox acquired — cannot download")
        return

    os.makedirs(directory, exist_ok=True)

    dump_resp = klavis.get_workspace_download_url(sandbox_id)
    if not dump_resp or "download_url" not in dump_resp:
        return

    with httpx.stream("GET", dump_resp["download_url"], timeout=timeout) as dl:
        dl.raise_for_status()
        buf = io.BytesIO()
        for chunk in dl.iter_bytes():
            buf.write(chunk)
        buf.seek(0)
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall(path=directory, filter="data")


def download_and_print_workspace(klavis: KlavisSandbox, directory: str, timeout: int = 120) -> None:
    """Download workspace into *directory* and print a coloured file listing."""
    print(f"{_CYAN}[download]{_RST} Downloading workspace …")
    try:
        download_workspace(klavis, directory, timeout=timeout)
        print(f"{_GREEN}[download]{_RST} Saved to {directory}")
        print_file_tree(directory, label="download")
    except Exception as e:
        print(f"{_RED}[download]{_RST} Download failed: {e}")


# ========================== Log Helpers ==========================

def print_file_tree(directory: str, label: str = "verify") -> None:
    """Print a colored file tree for *directory*."""
    files = sorted(Path(directory).rglob("*"))
    if files:
        print(f"  {_GREEN}[{label}]{_RST} {len(files)} items found:")
        for f in files:
            rel = f.relative_to(directory)
            if f.is_dir():
                print(f"    {_YELLOW}📁 {rel}/{_RST}")
            else:
                size = f.stat().st_size
                print(f"    {_DIM}📄 {rel}  ({size:,} bytes){_RST}")
    else:
        print(f"  {_RED}[{label}]{_RST} WARNING: directory is empty!")


# ========================== Task Loading & Evaluation ==========================

def load_task(task_name: str) -> dict:
    """Load task config, prompt, and system prompt from the task directory."""
    task_dir = TASKS_DIR / task_name

    config = json.loads((task_dir / "task_config.json").read_text())
    task_str = (task_dir / "docs" / "task.md").read_text()
    system_prompt_raw = (task_dir / "docs" / "agent_system_prompt.md").read_text()

    system_prompt = system_prompt_raw.replace(
        "!!<<<<||||workspace_dir||||>>>>!!", "/data"
    )
    system_prompt += (
        "\nPlease complete the given task independently. "
        "Do not seek confirmation or additional feedback from the user. "
        "You should handle all situations on your own, as the user will not provide any further information."
    ) # original Toolathlon

    tarball = task_dir / "initial_workspace" / "initial_workspace.tar.gz"

    needed_servers = config.get("needed_mcp_servers") or config.get("mcp_servers_required", [])
    needed_local_tools = config.get("needed_local_tools", [])

    groundtruth_ws = task_dir / "groundtruth_workspace"

    # Load email credentials if present (used as x-email-config header for the emails MCP server)
    # Some tasks use "emails_config.json", others use "email_config.json".
    emails_config_path = task_dir / "emails_config.json"
    if not emails_config_path.exists():
        emails_config_path = task_dir / "email_config.json"
    emails_config = json.loads(emails_config_path.read_text()) if emails_config_path.exists() else None

    return {
        "name": task_name,
        "needed_servers": needed_servers,
        "needed_local_tools": needed_local_tools,
        "task_str": task_str,
        "system_prompt": system_prompt,
        "tarball": str(tarball) if tarball.exists() else None,
        "eval_dir": task_dir / "evaluation",
        "groundtruth_workspace": str(groundtruth_ws) if groundtruth_ws.exists() else None,
        "emails_config": emails_config,
    }


# The four google_cloud_allowed_* keys that tasks may set in token_key_session.py.
_GOOGLE_CLOUD_ALLOWED_KEYS = [
    "google_cloud_allowed_buckets",
    "google_cloud_allowed_bigquery_datasets",
    "google_cloud_allowed_log_buckets",
    "google_cloud_allowed_instances",
]


def _load_google_cloud_config(task_dir: Path) -> Optional[Dict[str, str]]:
    """Execute the task's token_key_session.py and extract google_cloud_allowed_* values."""
    tks_path = task_dir / "token_key_session.py"
    if not tks_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_tks", tks_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        session = getattr(mod, "all_token_key_session", {})
        cfg = {k: str(session[k]) for k in _GOOGLE_CLOUD_ALLOWED_KEYS if k in session}
        return cfg or None
    except Exception as e:
        print(f"{_YELLOW}[warn] Failed to load google_cloud config from {tks_path}: {e}{_RST}")
        return None


# Path to the _hijack/ directory containing sitecustomize.py.
# When prepended to PYTHONPATH, Python auto-imports it at startup, which
# monkey-patches socket.getaddrinfo() and/or builtins.open() to redirect
# network/file access as specified by HIJACK_* env vars.
SOCKET_HIJACK_DIR = str(PROJECT_ROOT / "_hijack")


def _build_subprocess_env(auth_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build a subprocess env dict with PYTHONPATH and optional auth vars."""
    env = os.environ.copy()
    pythonpath_parts = [str(PROJECT_ROOT)]
    if auth_env:
        env.update(auth_env)
    # If any hijack env vars are set, prepend _hijack/ so that
    # sitecustomize.py is auto-loaded and applies the relevant monkeypatches
    # (socket redirect for IMAP/SMTP, file-open redirect for Google creds).
    if (env.get("HIJACK_IMAP_HOST")
            or env.get("HIJACK_SMTP_HOST")
            or env.get("HIJACK_GOOGLE_CREDENTIALS_PATH")
            or env.get("HIJACK_GCP_SERVICE_ACCOUNT_PATH")):
        pythonpath_parts.insert(0, SOCKET_HIJACK_DIR)
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def _create_tarball_from_directory(src_dir: Path, task_name: str) -> Optional[str]:
    """Create a tar.gz from all files in *src_dir*; return the tarball path."""
    items = list(src_dir.iterdir())
    if not items:
        return None
    tarball = os.path.join(
        tempfile.gettempdir(),
        f"workspace_{task_name.replace('/', '_')}.tar.gz",
    )
    with tarfile.open(tarball, "w:gz") as tar:
        for item in items:
            tar.add(str(item), arcname=item.name)
    return tarball


def run_preprocess(task: dict, auth_env: Optional[Dict[str, str]] = None, launch_time: Optional[str] = None) -> Optional[str]:
    """Run ``preprocess/main.py`` if present; return tarball path for upload.

    Workspace resolution order (first match wins):
      1. preprocess/main.py exists  → run it, tarball is built from its output.
      2. initial_workspace.tar.gz   → use the pre-built tarball directly.
      3. initial_workspace/ dir has raw files (e.g. PDFs) but no tar.gz and no
         preprocess script → create a tarball on-the-fly so those files still
         get uploaded to the Klavis sandbox.

    Note: across finalpool tasks, the breakdown is:
      - ~62 tasks have only loose files (handled by case 3)
      - ~10 tasks have a pre-built tar.gz (handled by case 2)
      -   2 tasks have both tar.gz + loose files (both have preprocess scripts → case 1)
      - ~27 tasks have no initial_workspace at all (no upload needed)
    Cases with mixed content are safe because they always have a preprocess script.
    """
    preprocess_main = TASKS_DIR / task["name"] / "preprocess" / "main.py"
    initial_ws = TASKS_DIR / task["name"] / "initial_workspace"

    if not preprocess_main.exists():
        if task.get("tarball"):
            return task["tarball"]
        if initial_ws.exists() and initial_ws.is_dir() and any(initial_ws.iterdir()):
            print(f"{_CYAN}[preprocess]{_RST} No preprocess script; creating tarball from raw initial_workspace files \u2026")
            tarball = _create_tarball_from_directory(initial_ws, task["name"])
            if tarball:
                print_file_tree(str(initial_ws), label="initial_workspace")
            return tarball
        return None

    print(f"{_CYAN}[preprocess]{_RST} Running {preprocess_main.relative_to(TASKS_DIR)} \u2026")
    tmp = tempfile.mkdtemp(prefix="preprocess_ws_")

    initial_ws = TASKS_DIR / task["name"] / "initial_workspace"
    if initial_ws.exists() and initial_ws.is_dir():
        for item in initial_ws.iterdir():
            dest = Path(tmp) / item.name
            if item.is_dir():
                shutil.copytree(str(item), str(dest), dirs_exist_ok=True)
            else:
                shutil.copy2(str(item), str(dest))
        print(f"{_CYAN}[preprocess]{_RST} Copied initial_workspace into temp dir")

    # Copy task-root files.tar.gz into the temp dir if the preprocess expects it there.
    task_root_tar = TASKS_DIR / task["name"] / "files.tar.gz"
    if task_root_tar.exists() and not (Path(tmp) / "files.tar.gz").exists():
        shutil.copy2(str(task_root_tar), str(Path(tmp) / "files.tar.gz"))
        print(f"{_CYAN}[preprocess]{_RST} Copied task-root files.tar.gz into temp dir")

    env = _build_subprocess_env(auth_env)
    env["TZ"] = "UTC"
    preprocess_dir = preprocess_main.parent
    init = preprocess_dir / "__init__.py"
    created_init = not init.exists()
    if created_init:
        init.write_text("")
    try:
        task_dir = TASKS_DIR / task["name"]
        cmd = [sys.executable, "-m", f"{preprocess_dir.name}.main",
               "--agent_workspace", tmp]
        if launch_time:
            cmd += ["--launch_time", launch_time]
        rc = subprocess.run(
            cmd, cwd=str(task_dir), timeout=600, env=env,
        ).returncode
        if rc != 0:
            print(f"{_RED}[preprocess]{_RST} exited with code {rc}")
        if not any(Path(tmp).iterdir()):
            print(f"{_YELLOW}[preprocess]{_RST} No files generated")
            return task.get("tarball")

        print_file_tree(tmp, label="preprocess")
        tarball = os.path.join(tempfile.gettempdir(), f"preprocess_{task['name'].replace('/', '_')}.tar.gz")
        with tarfile.open(tarball, "w:gz") as tar:
            for item in Path(tmp).iterdir():
                tar.add(str(item), arcname=item.name)
        return tarball
    except Exception as e:
        print(f"{_RED}[preprocess]{_RST} Failed: {e}")
        return task.get("tarball")
    finally:
        if created_init:
            init.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


def evaluate(task: dict, workspace_path: str, auth_env: Optional[Dict[str, str]] = None, launch_time: Optional[str] = None) -> bool:
    """Try check_local.py first, then evaluation/main.py as a module."""
    eval_dir = task["eval_dir"]

    check_local = eval_dir / "check_local.py"
    if check_local.exists():
        spec = importlib.util.spec_from_file_location("check_local", str(check_local))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "check_file_structure"):
            return mod.check_file_structure(workspace_path)

    eval_main = eval_dir / "main.py"
    if eval_main.exists():
        init = eval_dir / "__init__.py"
        created = not init.exists()
        if created:
            init.write_text("")
        env = _build_subprocess_env(auth_env)
        # Eval scripts assume datetime.now() returns UTC (they format local
        # time with a hardcoded +00:00 offset).  Force UTC in the subprocess
        # so the time filters are correct regardless of the host timezone.
        env["TZ"] = "UTC"
        # Create an empty res.json because some script expect it to exist and will error if it's missing.
        res_log_file = eval_dir / "res.json"
        res_log_file.write_text('{"messages": []}')
        try:
            cmd = [
                sys.executable, "-m", f"{eval_dir.name}.main",
                "--agent_workspace", workspace_path, "--res_log_file", str(res_log_file),
            ]
            if task.get("groundtruth_workspace"):
                cmd += ["--groundtruth_workspace", task["groundtruth_workspace"]]
            if launch_time:
                cmd += ["--launch_time", launch_time]
            return subprocess.run(
                cmd,
                cwd=str(TASKS_DIR / task["name"]),
                env=env,
            ).returncode == 0
        finally:
            if created:
                init.unlink(missing_ok=True)

    print("[eval] No evaluation script found — skipping")
    return True


# ========================== Local Tool Resolution ==========================

def _resolve_local_tools(needed_local_tools: List[str]) -> list:
    """Resolve needed_local_tools names into FunctionTool instances."""
    tools = []
    for name in needed_local_tools:
        tool_or_toolset = LOCAL_TOOL_MAPPINGS.get(name)
        if tool_or_toolset is None:
            print(f"{_YELLOW}[local_tools]{_RST} Skipping unknown local tool: {name}")
            continue
        if isinstance(tool_or_toolset, list):
            tools.extend(tool_or_toolset)
        else:
            tools.append(tool_or_toolset)
    return tools


# ========================== Task Runner ==========================

async def run_task(
    task_name: str,
    model: str = DEFAULT_MODEL,
    max_turns: int = 25,
):
    """End-to-end: sandbox → upload → agent run → download → evaluate."""

    task = load_task(task_name)
    print(f"\n{'='*60}")
    print(f"  Task     : {task['name']}")
    print(f"  Model    : {model}")
    print(f"  MaxTurns : {max_turns}")
    print(f"{'='*60}\n")

    klavis = KlavisSandbox()

    # On SIGINT/SIGTERM, always release sandboxes then exit.
    def _signal_cleanup(signum, frame):
        print(f"\n[cleanup] Caught signal — releasing sandboxes …")
        try:
            klavis.cleanup_temp_files()
            klavis.release_all()
            print("[cleanup] Sandboxes released")
        except Exception:
            pass
        os._exit(1)

    signal.signal(signal.SIGINT, _signal_cleanup)
    signal.signal(signal.SIGTERM, _signal_cleanup)

    try:
        all_requested = task["needed_servers"]
        if "python_execute" in task["needed_local_tools"]:
            all_requested.append("code-executor")
        server_urls = klavis.acquire_for_servers(all_requested)
        if not server_urls:
            print("ERROR: Failed to acquire any sandbox servers")
            return False
        local_tools = _resolve_local_tools(task.get("needed_local_tools", []))
        if local_tools:
            tool_names = [t.name for t in local_tools]
            print(f"  {_YELLOW}Local tools: {_GREEN}{tool_names}{_RST}")
        sandbox_id = klavis.get_local_sandbox_id()
        print(f"[sandbox] id={sandbox_id}")
        print(f"  {_YELLOW}Needed/Required MCP Servers:       {_BLUE}{all_requested}{_RST}")
        print(f"  {_YELLOW}Actually Connected Klavis Servers: {_GREEN}{list(server_urls.keys())}{_RST}")
        if local_tools:
            print(f"  {_YELLOW}Local Tools (non-Klavis):          {_GREEN}{[t.name for t in local_tools]}{_RST}")

        launch_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %A")

        # Build per-server MCP headers. The emails server requires an
        # x-email-config header containing the base64-encoded user credentials
        # (email, password, name) so the MCP server knows which account to use.
        emails_config = task.get("emails_config")
        server_headers: Dict[str, Dict[str, str]] = {}
        if emails_config:
            header_payload = {
                "email": emails_config["email"],
                "password": emails_config["password"],
                "name": emails_config["name"],
            }
            email_cfg_b64 = base64.b64encode(json.dumps(header_payload).encode()).decode()
            server_headers["emails"] = {"x-email-config": email_cfg_b64}
            print(f"  {_YELLOW}Email config header set for: {header_payload['email']}{_RST}")

        # Inject KLAVIS_MCP_SERVER_URLS into auth_env so that child processes
        # (preprocess/evaluation scripts) using utils.mcp.tool_servers can
        # connect to Klavis MCP servers without needing YAML config files.
        klavis_mcp_env = {}
        for name, url in server_urls.items():
            entry: Dict = {"url": url}
            if name in server_headers:
                entry["headers"] = server_headers[name]
            klavis_mcp_env[name] = entry
        klavis.auth_env["KLAVIS_MCP_SERVER_URLS"] = json.dumps(klavis_mcp_env)

        tarball = run_preprocess(task, auth_env=klavis.auth_env, launch_time=launch_time)
        if tarball and sandbox_id:
            upload_workspace_tarball(klavis, tarball)
        
        # After preprocess, some tasks (e.g. nhl-b2b-analysis) write a Google
        # Drive folder_id to files/folder_id.txt.  Pass it as a header to the
        # google_sheet MCP server so it knows which folder to operate on.
        folder_id_file = TASKS_DIR / task["name"] / "files" / "folder_id.txt"
        if folder_id_file.exists() and "google_sheet" in server_urls:
            folder_id = folder_id_file.read_text().strip()
            server_headers.setdefault("google_sheet", {})["x-sheets-folder-id"] = folder_id
            # Also update KLAVIS_MCP_SERVER_URLS so eval/child processes see the header.
            klavis_mcp_env = json.loads(klavis.auth_env.get("KLAVIS_MCP_SERVER_URLS", "{}"))
            if "google_sheet" in klavis_mcp_env:
                klavis_mcp_env["google_sheet"].setdefault("headers", {})["x-sheets-folder-id"] = folder_id
                klavis.auth_env["KLAVIS_MCP_SERVER_URLS"] = json.dumps(klavis_mcp_env)
            print(f"  {_YELLOW}Google Sheets folder_id header set: {folder_id}{_RST}")

        # google-cloud: pass allowed resource headers (buckets, bigquery, etc.)
        # Loaded after preprocess because some values come from files it generates.
        gc_config = _load_google_cloud_config(TASKS_DIR / task["name"])
        if gc_config and "google-cloud" in server_urls:
            gc_headers = {f"x-{k.replace('_', '-')}": v for k, v in gc_config.items()}
            server_headers.setdefault("google-cloud", {}).update(gc_headers)
            # Update KLAVIS_MCP_SERVER_URLS so eval/child processes see the headers.
            klavis_mcp_env = json.loads(klavis.auth_env.get("KLAVIS_MCP_SERVER_URLS", "{}"))
            if "google-cloud" in klavis_mcp_env:
                klavis_mcp_env["google-cloud"].setdefault("headers", {}).update(gc_headers)
                klavis.auth_env["KLAVIS_MCP_SERVER_URLS"] = json.dumps(klavis_mcp_env)
            print(f"  {_YELLOW}Google Cloud headers set: {list(gc_headers.keys())}{_RST}")

        mcp_servers = []
        for name, url in server_urls.items():
            params: Dict = {"url": url}
            if name in server_headers:
                params["headers"] = server_headers[name]
            mcp_servers.append(
                MCPServerStreamableHttp(
                    params=params,
                    name=name,
                    cache_tools_list=True,
                    client_session_timeout_seconds=600,
                )
            )

        async with MCPServerManager(mcp_servers) as manager:
            agent = Agent(
                name="TaskAgent",
                instructions=task["system_prompt"],
                model=model,
                mcp_servers=manager.active_servers,
                tools=local_tools or [],
                model_settings=ModelSettings(parallel_tool_calls=True),
            )

            print(f"\n[agent] Running …\n")
            result = await Runner.run(
                starting_agent=agent,
                input=task["task_str"],
                max_turns=max_turns,
                hooks=ToolLoggingHooks(),
                context={"_agent_workspace": "/data"},
            )
            print(f"\n[agent] Final output:\n{result.final_output[:600]}\n")

        ws_dir = OUTPUT_DIR / task_name / "workspace"
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
        ws_dir.mkdir(parents=True, exist_ok=True)

        if sandbox_id:
            download_and_print_workspace(klavis, str(ws_dir))

        print("\n[eval] Running evaluation …")
        passed = evaluate(task, str(ws_dir), auth_env=klavis.auth_env, launch_time=launch_time)
        print(f"\n{'='*60}")
        print(f"  Result: {'PASS ✓' if passed else 'FAIL ✗'}")
        print(f"{'='*60}")

        return passed

    finally:
        klavis.cleanup_temp_files()
        klavis.release_all()
        print("[cleanup] Sandboxes released")

# ========================== Parallel Execution ==========================

def _load_conflict_groups() -> List[List[str]]:
    """Load conflict groups from task_conflict.json (tasks that must not run concurrently)."""
    conflict_file = TASKS_DIR / "tasks" / "finalpool" / "task_conflict.json"
    if not conflict_file.exists():
        return []
    data = json.loads(conflict_file.read_text())
    return data.get("conflict_groups", [])


def _task_short_name(task_path: str) -> str:
    """Extract the short task name from a path like 'tasks/finalpool/arrange-workspace'."""
    return Path(task_path).name


def _resolve_task_list(raw: List[str]) -> List[str]:
    """Expand a task list — entries can be paths or a .txt file with one task per line."""
    tasks: List[str] = []
    for entry in raw:
        p = Path(entry)
        if p.suffix == ".txt" and p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    tasks.append(line)
        else:
            tasks.append(entry)
    return tasks


# The 52 Klavis-supported tasks (status=ready in task_status_in_klavis_sandbox.md).
# Only these have all required MCP servers available in the Klavis sandbox.
SUPPORTED_TASKS = [
    "ab-testing",
    "academic-warning",
    "apply-phd-email",
    "arrange-workspace",
    "course-assistant",
    "courses-ta-hws",
    "detect-revised-terms",
    "email-paper-homepage",
    "excel-data-transformation",
    "excel-market-research",
    "experiments-recordings",
    "filter-low-selling-products",
    "flagged-transactions",
    "game-statistics",
    "git-bug-hunt",
    "git-repo",
    "huggingface-upload",
    "imagenet",
    "interview-report",
    "inventory-sync",
    "landing-task-reminder",
    "live-transactions",
    "machine-operating",
    "merge-hf-datasets",
    "music-analysis",
    "nhl-b2b-analysis",
    "notion-hr",
    "notion-personal-website",
    "paper-checker",
    "payable-invoice-checker",
    "personal-website-construct",
    "ppt-analysis",
    "price-comparison",
    "privacy-desensitization",
    "reimbursement-form-filler",
    "sales-accounting",
    "set-conf-cr-ddl",
    "sla-timeout-monitor",
    "student-interview",
    "sync-todo-to-readme",
    "task-tracker",
    "travel-expense-reimbursement",
    "university-course-selection",
    "update-material-inventory",
    "wandb-best-score",
    "wandb-shortest-length",
    "woocommerce-customer-survey",
    "woocommerce-new-product",
    "woocommerce-new-welcome",
    "woocommerce-product-recall",
    "woocommerce-stock-alert",
    "woocommerce-update-cover",
]


def _get_all_ready_tasks() -> List[str]:
    """Return paths for the 52 supported tasks that exist on disk."""
    base = TASKS_DIR / "tasks" / "finalpool"
    if not base.exists():
        return []
    return sorted(
        f"tasks/finalpool/{name}"
        for name in SUPPORTED_TASKS
        if (base / name / "task_config.json").exists()
    )


async def run_tasks_parallel(
    task_names: List[str],
    model: str = DEFAULT_MODEL,
    max_turns: int = 100,
    max_parallel: int = 10,
    log_dir: str = "logs",
) -> Dict[str, Optional[bool]]:
    """Run multiple tasks with bounded parallelism, respecting conflict groups.

    Each task is launched as a **separate subprocess** so that:
      - stdout/stderr are naturally isolated (no global sys.stdout conflict)
      - blocking subprocess.run() calls inside run_preprocess/evaluate
        don't stall the event loop or other tasks

    Each task's full output is captured in ``<log_dir>/<task_short_name>.log``.
    A summary is printed to the terminal after all tasks finish.

    Conflict groups (from task_conflict.json) are serialised: tasks within the
    same group run one-at-a-time while tasks in different groups (and
    non-conflicting tasks) run in parallel up to *max_parallel*.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_log_dir = os.path.join(log_dir, f"run_{timestamp}")
    os.makedirs(run_log_dir, exist_ok=True)

    # Build conflict-group lookup: short_name → group_id
    conflict_groups = _load_conflict_groups()
    task_to_group: Dict[str, int] = {}
    for gid, group in enumerate(conflict_groups):
        for t in group:
            task_to_group[t] = gid

    # One lock per conflict group (serialises tasks within the same group)
    group_locks: Dict[int, asyncio.Lock] = {}
    for gid in set(task_to_group.values()):
        group_locks[gid] = asyncio.Lock()

    semaphore = asyncio.Semaphore(max_parallel)
    results: Dict[str, Optional[bool]] = {}
    start_time = datetime.now()

    # Path to this script — used to launch child processes.
    this_script = str(Path(__file__).resolve())

    # No need to track child processes for signal delivery.
    # Ctrl+C sends SIGINT to the entire foreground process group,
    # so all children receive it automatically.  Each child runs in
    # --task mode with its own signal handler that calls
    # klavis.release_all() before exiting.

    async def _wrapped(task_name: str):
        short = _task_short_name(task_name)
        log_path = os.path.join(run_log_dir, f"{short}.log")
        gid = task_to_group.get(short)
        lock = group_locks.get(gid) if gid is not None else None

        async with semaphore:
            if lock:
                await lock.acquire()
            try:
                print(f"{_CYAN}[parallel]{_RST} Starting  {_YELLOW}{short}{_RST}  →  {log_path}")
                # Launch as a child process — completely isolated stdout/stderr
                # and its own event loop, so blocking subprocess calls inside
                # run_preprocess/evaluate don't affect other tasks.
                cmd = [
                    sys.executable, "-u", this_script,
                    "--task", task_name,
                    "--model", model,
                    "--max-turns", str(max_turns),
                ]
                with open(log_path, "w") as log_fh:
                    log_fh.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                                 f"Command: {' '.join(cmd)}\n{'='*80}\n")
                    log_fh.flush()
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=log_fh,
                        stderr=log_fh,
                        cwd=str(PROJECT_ROOT),
                    )
                    returncode = await proc.wait()

                passed = returncode == 0
                results[task_name] = passed
                status = f"{_GREEN}PASS{_RST}" if passed else f"{_RED}FAIL{_RST}"
                print(f"{_CYAN}[parallel]{_RST} Finished  {_YELLOW}{short}{_RST}  →  {status}")
            except asyncio.CancelledError:
                # Task was cancelled due to Ctrl+C — don't log as an unexpected error
                results[task_name] = None
                raise
            except Exception as exc:
                results[task_name] = None
                print(f"{_RED}[parallel]{_RST} Error     {_YELLOW}{short}{_RST}  →  {exc}")
                import traceback
                with open(log_path, "a") as fh:
                    fh.write(f"\n\n{'='*60}\nUNHANDLED EXCEPTION\n{'='*60}\n")
                    traceback.print_exc(file=fh)
            finally:
                if lock:
                    lock.release()

    try:
        await asyncio.gather(*[_wrapped(t) for t in task_names])
    except (asyncio.CancelledError, KeyboardInterrupt):
        print(f"\n{_RED}[parallel]{_RST} Interrupted — children received SIGINT and will release their sandboxes")

    # ---- Summary ----
    elapsed = datetime.now() - start_time
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    errors = sum(1 for v in results.values() if v is None)

    print(f"\n{'='*70}")
    print(f"  PARALLEL RUN SUMMARY   ({elapsed.total_seconds():.1f}s elapsed)")
    print(f"  Logs directory: {run_log_dir}")
    print(f"{'='*70}")
    print(f"  {'Task':<45} {'Result':>10}")
    print(f"  {'-'*45} {'-'*10}")
    for t in task_names:
        short = _task_short_name(t)
        v = results.get(t)
        if v is True:
            tag = f"{_GREEN}PASS{_RST}"
        elif v is False:
            tag = f"{_RED}FAIL{_RST}"
        else:
            tag = f"{_RED}ERROR{_RST}"
        print(f"  {short:<45} {tag:>10}")
    print(f"\n  Passed: {passed}  |  Failed: {failed}  |  Errors: {errors}  |  Total: {len(results)}")
    print(f"{'='*70}\n")

    # Write a machine-readable summary JSON alongside the logs
    summary = {
        "timestamp": timestamp,
        "model": model,
        "max_turns": max_turns,
        "max_parallel": max_parallel,
        "elapsed_seconds": round(elapsed.total_seconds(), 1),
        "results": {_task_short_name(t): {True: "PASS", False: "FAIL"}.get(results.get(t), "ERROR") for t in task_names},
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }
    summary_path = os.path.join(run_log_dir, "summary.json")
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"  Summary written to {summary_path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Toolathlon Runner — run one or many tasks (with parallel support)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Run a single task (output goes to terminal)
  python toolathlon_task_run_example.py --task tasks/finalpool/arrange-workspace

  # Run multiple tasks in parallel (default 10 workers, logs to files)
  python toolathlon_task_run_example.py --tasks tasks/finalpool/arrange-workspace tasks/finalpool/git-repo

  # Run tasks listed in a file
  python toolathlon_task_run_example.py --tasks my_tasks.txt --parallel 5

  # Run ALL 52 supported tasks (default when no --task/--tasks given)
  python toolathlon_task_run_example.py
  python toolathlon_task_run_example.py --parallel 5
  python toolathlon_task_run_example.py --all --parallel 10
""",
    )
    parser.add_argument("--task", default=None,
                        help="Single task path (output to terminal). e.g. tasks/finalpool/arrange-workspace")
    parser.add_argument("--tasks", nargs="+", default=None,
                        help="Multiple task paths (or a .txt file). Each task's output is saved to a log file.")
    parser.add_argument("--all", action="store_true",
                        help="Run all 52 supported tasks in parallel (this is the default when no --task/--tasks given)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--max-turns", type=int, default=100, help="Max agent tool-call turns")
    parser.add_argument("--parallel", type=int, default=10,
                        help="Max number of tasks to run concurrently (default: 10)")
    parser.add_argument("--log-dir", default="logs",
                        help="Directory for per-task log files (default: logs/)")
    args = parser.parse_args()

    # Determine which mode to use
    modes_set = sum([args.task is not None, args.tasks is not None, args.all])
    if modes_set > 1:
        parser.error("Use exactly one of --task, --tasks, or --all")

    if args.task:
        # Single-task mode: backward compatible, prints to terminal.
        # run_task() installs its own SIGINT/SIGTERM handler to ensure
        # sandbox cleanup even on repeated Ctrl+C.
        result = asyncio.run(run_task(args.task, args.model, args.max_turns))
        sys.exit(0 if result else 1)

    elif args.tasks:
        task_list = _resolve_task_list(args.tasks)
        if not task_list:
            print(f"{_RED}No tasks resolved from --tasks{_RST}")
            sys.exit(1)
        print(f"{_CYAN}[parallel]{_RST} {len(task_list)} tasks, running with parallelism={args.parallel}")
        try:
            results = asyncio.run(run_tasks_parallel(
                task_list, args.model, args.max_turns, args.parallel, args.log_dir,
            ))
        except KeyboardInterrupt:
            print(f"\n{_RED}[main]{_RST} Interrupted")
            results = {}
        any_fail = any(v is not True for v in results.values()) if results else True
        sys.exit(1 if any_fail else 0)

    else:
        # Default: run all 52 supported tasks in parallel (same as --all)
        task_list = _get_all_ready_tasks()
        if not task_list:
            print(f"{_RED}No supported tasks found under tasks/finalpool/{_RST}")
            sys.exit(1)
        print(f"{_CYAN}[parallel]{_RST} Running {len(task_list)} supported tasks with parallelism={args.parallel}")
        try:
            results = asyncio.run(run_tasks_parallel(
                task_list, args.model, args.max_turns, args.parallel, args.log_dir,
            ))
        except KeyboardInterrupt:
            print(f"\n{_RED}[main]{_RST} Interrupted")
            results = {}
        any_fail = any(v is not True for v in results.values()) if results else True
        sys.exit(1 if any_fail else 0)


if __name__ == "__main__":
    main()
