"""
Toolathlon task runner using Klavis Sandbox + OpenAI Agents SDK.

Usage:
    export KLAVIS_API_KEY=...
    export ANTHROPIC_API_KEY=...
    export OPENAI_API_KEY=...
    python toolathlon_task_run_example.py --task [task_name]
"""

import asyncio
import io
import json
import os
import sys
import shutil
import subprocess
import tempfile
import tarfile
import importlib.util
import argparse
from pathlib import Path
from typing import Dict, Optional, List

import httpx
from dotenv import load_dotenv
from agents import Agent, Runner, RunHooks
from agents.mcp import MCPServerManager, MCPServerStreamableHttp

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

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
DEFAULT_MODEL = "litellm/claude-sonnet-4-5-20250929"

_GREEN = "\033[92m"
_CYAN = "\033[96m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_DIM = "\033[2m"
_RST = "\033[0m"

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
}

TASK_SERVER_TO_SANDBOX_NAME = {
    "arxiv-latex": "arxiv_latex",
    "google_sheet": "google_sheets",
    "wandb": "weights_and_biases",
}

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
    "snowflake": {
        "SNOWFLAKE_ACCOUNT": "KLAVIS_SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_WAREHOUSE": "KLAVIS_SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_ROLE": "KLAVIS_SNOWFLAKE_ROLE",
        "SNOWFLAKE_USER": "KLAVIS_SNOWFLAKE_USER",
        "SNOWFLAKE_PRIVATE_KEY": "KLAVIS_SNOWFLAKE_PRIVATE_KEY",
        "SNOWFLAKE_DATABASE": "KLAVIS_SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA": "KLAVIS_SNOWFLAKE_SCHEMA",
    },
}


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
        return overrides

    def _apply_sandbox_auth(self, server_name: str, sandbox_id: str):
        """Fetch auth_data from Klavis sandbox and store in self.auth_env."""
        mapping = SANDBOX_AUTH_ENV_MAPPING.get(server_name)
        if not mapping:
            return
        auth = (self.get_sandbox_details(server_name, sandbox_id) or {}).get("auth_data", {})
        for key, env_var in mapping.items():
            if (val := auth.get(key)) is not None:
                self.auth_env[env_var] = str(val)
                print(f"[Klavis] Set {env_var}")

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
        "\nWhen you believe the task is completed, "
        "respond with a brief summary without calling any more tools."
    )

    tarball = task_dir / "initial_workspace" / "initial_workspace.tar.gz"

    needed_servers = config.get("needed_mcp_servers") or config.get("mcp_servers_required", [])
    needed_local_tools = config.get("needed_local_tools", [])

    groundtruth_ws = task_dir / "groundtruth_workspace"

    return {
        "name": task_name,
        "needed_servers": needed_servers,
        "needed_local_tools": needed_local_tools,
        "task_str": task_str,
        "system_prompt": system_prompt,
        "tarball": str(tarball) if tarball.exists() else None,
        "eval_dir": task_dir / "evaluation",
        "groundtruth_workspace": str(groundtruth_ws) if groundtruth_ws.exists() else None,
    }


def _build_subprocess_env(auth_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build a subprocess env dict with PYTHONPATH and optional auth vars."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    if auth_env:
        env.update(auth_env)
    return env


def run_preprocess(task: dict, auth_env: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Run ``preprocess/main.py`` if present; return tarball path for upload."""
    preprocess_main = TASKS_DIR / task["name"] / "preprocess" / "main.py"
    if not preprocess_main.exists():
        return task.get("tarball")

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

    env = _build_subprocess_env(auth_env)
    try:
        rc = subprocess.run(
            [sys.executable, str(preprocess_main), "--agent_workspace", tmp],
            cwd=str(preprocess_main.parent), timeout=600, env=env,
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
        shutil.rmtree(tmp, ignore_errors=True)


def evaluate(task: dict, workspace_path: str, auth_env: Optional[Dict[str, str]] = None) -> bool:
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
        try:
            cmd = [
                sys.executable, "-m", f"{eval_dir.name}.main",
                "--agent_workspace", workspace_path,
            ]
            if task.get("groundtruth_workspace"):
                cmd += ["--groundtruth_workspace", task["groundtruth_workspace"]]
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
    try:
        server_urls = klavis.acquire_for_servers(task["needed_servers"])
        if not server_urls:
            print("ERROR: Failed to acquire any sandbox servers")
            return False

        sandbox_id = klavis.get_local_sandbox_id()
        print(f"[sandbox] id={sandbox_id}")
        print(f"  {_YELLOW}Needed/Required MCP Servers:       \033[94m{task['needed_servers']}{_RST}")
        print(f"  {_YELLOW}Actually Connected Klavis Servers: {_GREEN}{list(server_urls.keys())}{_RST}")

        tarball = run_preprocess(task, auth_env=klavis.auth_env)
        if tarball and sandbox_id:
            upload_workspace_tarball(klavis, tarball)

        mcp_servers = [
            MCPServerStreamableHttp(
                params={"url": url},
                name=name,
                cache_tools_list=True,
                client_session_timeout_seconds=120,
            )
            for name, url in server_urls.items()
        ]

        local_tools = _resolve_local_tools(task.get("needed_local_tools", []))
        if local_tools:
            tool_names = [t.name for t in local_tools]
            print(f"  {_YELLOW}Local tools: {_GREEN}{tool_names}{_RST}")

        async with MCPServerManager(mcp_servers) as manager:
            agent = Agent(
                name="TaskAgent",
                instructions=task["system_prompt"],
                model=model,
                mcp_servers=manager.active_servers,
                tools=local_tools or [],
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
        passed = evaluate(task, str(ws_dir), auth_env=klavis.auth_env)
        print(f"\n{'='*60}")
        print(f"  Result: {'PASS ✓' if passed else 'FAIL ✗'}")
        print(f"{'='*60}")

        return passed

    finally:
        klavis.release_all()
        print("[cleanup] Sandboxes released")

def main():
    parser = argparse.ArgumentParser(description="Toolathlon Runner")
    parser.add_argument("--task", default="tasks/finalpool/arrange-workspace", help="Single task path under tasks/, e.g. tasks/finalpool/arrange-workspace")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name")
    parser.add_argument("--max-turns", type=int, default=50, help="Max agent tool-call turns")
    args = parser.parse_args()

    result = asyncio.run(run_task(args.task, args.model, args.max_turns))
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
