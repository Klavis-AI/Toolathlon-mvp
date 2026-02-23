# Toolathlon Task Runner — Minimal Working Example

A self-contained, minimal example for running [Toolathlon](https://github.com/toolathlon/toolathlon) benchmark tasks end-to-end using the **Klavis AI Sandbox API** and the **OpenAI Agents SDK**.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture Diagram](#architecture-diagram)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Task Directory Structure](#task-directory-structure)
- [Key Concepts](#key-concepts)
  - [Klavis Sandbox Types](#klavis-sandbox-types)
  - [MCP Transport: Streamable HTTP](#mcp-transport-streamable-http)
  - [Server Name Mappings](#server-name-mappings)
- [Credential Injection & Network/File Hijacking](#credential-injection--networkfile-hijacking)
  - [Why This Is Needed](#why-this-is-needed)
  - [The Three Credential Injection Strategies](#the-three-credential-injection-strategies)
  - [Strategy 1: Environment Variables (Direct)](#strategy-1-environment-variables-direct)
  - [Strategy 2: Network Hijack (Socket Monkeypatch)](#strategy-2-network-hijack-socket-monkeypatch)
  - [Strategy 3: File Hijack (open/stat Monkeypatch)](#strategy-3-file-hijack-openstat-monkeypatch)
  - [How \_build\_subprocess\_env Ties It Together](#how-_build_subprocess_env-ties-it-together)
  - [Decision Table: Which Strategy For Which Server](#decision-table-which-strategy-for-which-server)
  - [Implementing This Yourself](#implementing-this-yourself)

---

## How It Works

The runner automates the full lifecycle of a Toolathlon benchmark task:

1. **Load** the task definition (prompt, system prompt, required MCP servers) from disk.
2. **Acquire** remote sandbox environments from Klavis AI — each providing MCP tool servers (filesystem, terminal, git, etc.).
3. **Preprocess** — run any task-specific setup scripts to prepare the initial workspace (needs sandbox auth credentials from step 2).
4. **Upload** the initial workspace tarball to the remote sandbox.
5. **Run the agent** — an LLM-powered agent uses MCP tools via the sandbox to complete the task.
6. **Download** the resulting workspace from the sandbox.
7. **Evaluate** — run the task's evaluation script to check correctness (PASS/FAIL).
8. **Cleanup** — release all sandbox resources.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       Your Machine (Local)                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │         toolathlon_task_run_example.py  (main process)            │  │
│  │                                                                   │  │
│  │  1. load_task()        ─── reads task config & prompts            │  │
│  │                                                                   │  │
│  │  2. KlavisSandbox      ─── acquires sandboxes, extracts auth_data │  │
│  │     acquire_for_         ┌──────────────────────────────────────┐ │  │
│  │      servers()           │ auth_env dict (built from auth_data) │ │  │
│  │                          │                                      │ │  │
│  │                          │ • KLAVIS_GITHUB_TOKEN, ...           │ │  │
│  │                          │ • HIJACK_IMAP_HOST/PORT, ...         │ │  │
│  │                          │ • HIJACK_GOOGLE_CREDENTIALS_PATH, .. │ │  │
│  │                          └──────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  │  3. run_preprocess()   ─── subprocess ──  (auth_env injected)     │  │
│  │     ┌───────────────────────────────────────────────────────────┐ │  │
│  │     │ SUBPROCESS: preprocess/main.py                            │ │  │
│  │     │                                                           │ │  │
│  │     │  _hijack/sitecustomize.py auto-loaded via PYTHONPATH      │ │  │
│  │     │  (only when HIJACK_* env vars are present)                │ │  │
│  │     │   • socket.getaddrinfo patched → redirect IMAP/SMTP       │ │  │
│  │     │   • builtins.open/os.stat patched → redirect cred files   │ │  │
│  │     └───────────────────────────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  │  4. upload_workspace() ─── sends tar.gz to sandbox                │  │
│  │  5. Agent + Runner  ─── LLM ↔ Klavis MCP (direct HTTP, no hijack) │  |
│  │  6. download_workspace() ─── retrieves results                    │  │
│  │                                                                   │  │
│  │  7. evaluate()         ─── subprocess (auth_env injected)         │  │
│  │     ┌───────────────────────────────────────────────────────────┐ │  │
│  │     │ SUBPROCESS: evaluation/main.py                            │ │  │
│  │     │                                                           │ │  │
│  │     │  _hijack/sitecustomize.py auto-loaded via PYTHONPATH      │ │  │
│  │     │  (same mechanism as preprocess — only when needed)        │ │  │
│  │     │   • socket.getaddrinfo patched → redirect IMAP/SMTP       │ │  │
│  │     │   • builtins.open/os.stat patched → redirect cred files   │ │  │
│  │     └───────────────────────────────────────────────────────────┘ │  │
│  │                                                                   │  │
│  │  8. release_all()      ─── cleanup sandboxes + temp files         │  │
│  └──────────┬──────────────────────┬─────────────────────────────────┘  │
│             │                      │                                    │
│         LLM API calls         MCP tool calls                            │
│             │                      │                                    │
└─────────────┼──────────────────────┼────────────────────────────────────┘
              │                      │
              ▼                      ▼
   ┌──────────────────┐    ┌─────────────────────────────────────┐
   │   LLM Provider   │    │      Klavis AI Sandbox Cloud        │
   │                  │    │                                     │
   │  Claude / GPT /  │    │  ┌──────────────────────────────┐   │
   │  any litellm     │    │  │  Local Sandbox (shared VM)   │   │
   │  supported model │    │  │  ┌──────┐ ┌──────┐ ┌──────┐  │   │
   │                  │    │  │  │ fs   │ │ term │ │ git  │  │   │
   └──────────────────┘    │  │  │ MCP  │ │ MCP  │ │ MCP  │  │   │
                           │  │  └──────┘ └──────┘ └──────┘  │   │
                           │  │    /data  workspace          │   │
                           │  └──────────────────────────────┘   │
                           │                                     │
                           │  ┌──────────────────────────────┐   │
                           │  │ Individual Sandboxes         │   │
                           │  │  ┌────────┐  ┌────────────┐  │   │
                           │  │  │ github │  │ woocommerce│  │   │
                           │  │  │  MCP   │  │    MCP     │  │   │
                           │  │  └────────┘  └────────────┘  │   │
                           │  └──────────────────────────────┘   │
                           └─────────────────────────────────────┘
```

**Data flow during preprocess/evaluate subprocesses (hijack active here):**

```
subprocess (preprocess/eval script)
    │
    │  Python auto-imports _hijack/sitecustomize.py via PYTHONPATH
    │
    ├── imaplib.IMAP4("localhost", 1143)
    │       └── socket.getaddrinfo("localhost", 1143)
    │               └── [HIJACKED] → resolves to remote Klavis email IP:port
    │
    ├── open("configs/google_credentials.json")
    │       └── [HIJACKED] → opens /tmp/google_creds_XXXX.json instead
    │
    └── os.environ.get("KLAVIS_GITHUB_TOKEN")
            └── [NO HIJACK] → reads env var directly (set by auth_env)
```

**Credential flow (preprocess & evaluation scripts):**

```
Klavis API ──acquire──▶ auth_data (tokens, IPs, keys)
                              │
                    ┌─────────┴──────────────┐
                    ▼                        ▼
            Simple values              Complex values
            (tokens, URLs)             (private keys, JSON creds)
                    │                        │
                    ▼                        ▼
          Set as env vars           Write to temp files,
          (KLAVIS_GITHUB_TOKEN,     set HIJACK_* env vars
           KLAVIS_WOOCOMMERCE_*)    pointing to temp files
                    │                        │
                    └────────┬───────────────┘
                             ▼
                   _build_subprocess_env()
                   ┌────────────────────────┐
                   │ Merges auth_env into   │
                   │ subprocess environment │
                   │                        │
                   │ If HIJACK_* vars set:  │
                   │ prepend _hijack/ to    │
                   │ PYTHONPATH             │
                   └────────┬───────────────┘
                            ▼
               subprocess.run(preprocess/eval)
               ┌────────────────────────────┐
               │ Python auto-imports        │
               │ _hijack/sitecustomize.py   │
               │                            │
               │ • socket.getaddrinfo       │
               │   patched → redirects      │
               │   localhost IMAP/SMTP      │
               │                            │
               │ • builtins.open / os.stat  │
               │   patched → redirects      │
               │   credential file reads    │
               └────────────────────────────┘
```

---

## Prerequisites

| Requirement | Details |
|---|---|
| **Python** | 3.10+ |
| **Klavis API Key** | Sign up at [klavis.ai](https://klavis.ai) to get a `KLAVIS_API_KEY` |
| **LLM API Key** | At least one of: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (depending on which model you use) |

---

## Installation

```bash
# Clone this repo
git clone <repo-url>
cd Toolathlon-mvp

# Install dependencies
pip install -r requirements.txt
```

**`requirements.txt` contents:**
```
httpx
python-dotenv
openai-agents
addict
requests
tenacity
Pillow
litellm
```

---

## Quick Start

### 1. Set environment variables

Create a `.env` file in the project root (or export directly):

```bash
# .env
KLAVIS_API_KEY=your_klavis_api_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here    # if using Claude models
OPENAI_API_KEY=your_openai_key_here          # if using GPT models
```

### 2. Run a task

```bash
# Run the default task (arrange-workspace)
python toolathlon_task_run_example.py

# Run a specific task
python toolathlon_task_run_example.py --task tasks/finalpool/courses-ta-hws

# Use a different model
python toolathlon_task_run_example.py --task tasks/finalpool/arrange-workspace --model litellm/gpt-4o

# Increase max agent turns
python toolathlon_task_run_example.py --task tasks/finalpool/inventory-sync --max-turns 80
```

## Task Directory Structure

Each task lives under `tasks/finalpool/<task-name>/` and follows this canonical layout:

```
tasks/finalpool/<task-name>/
├── task_config.json                  # Required MCP servers & metadata
├── docs/
│   ├── task.md                       # Natural-language task prompt (sent to the agent)
│   ├── agent_system_prompt.md        # System prompt template (!!<<<<||||workspace_dir||||>>>>!! → /data)
│   ├── task_cn.md                    # (Optional) Chinese translation
│   └── agent_system_prompt_cn.md     # (Optional) Chinese system prompt
├── initial_workspace/
│   └── initial_workspace.tar.gz      # Starting files uploaded to the sandbox
├── preprocess/
│   └── main.py                       # (Optional) Setup script run before upload
├── evaluation/
│   ├── main.py                       # Evaluation entry point
│   └── check_local.py                # Core correctness checker
└── groundtruth_workspace/            # (Optional) Expected outputs for evaluation
```

### Key files explained

| File | Purpose |
|---|---|
| `task_config.json` | Declares `needed_mcp_servers` (list of server names the task requires) and optional metadata |
| `docs/task.md` | The exact prompt the agent receives as its input |
| `docs/agent_system_prompt.md` | System instructions for the agent. The placeholder `!!<<<<\|\|\|\|workspace_dir\|\|\|\|>>>>!!` is replaced with `/data` at runtime |
| `initial_workspace/initial_workspace.tar.gz` | Archive of files that get extracted into the sandbox's `/data` directory before the agent starts |
| `preprocess/main.py` | Optional script executed locally before upload. Receives `--agent_workspace <tmpdir>` and can modify the workspace |
| `evaluation/check_local.py` | Defines a `check_file_structure(workspace_path)` function that returns `True`/`False` |
| `evaluation/main.py` | CLI wrapper: `--agent_workspace <path> [--groundtruth_workspace <path>]` |

### Example `task_config.json`

```json
{
  "needed_mcp_servers": ["filesystem", "terminal", "pdf-tools", "excel"],
  "needed_local_tools": ["claim_done", "python_execute"],
  "meta": {}
}
```

---

## Key Concepts

### Klavis Sandbox Types

The Klavis API provides two types of sandboxes (both expose MCP servers over **Streamable HTTP** — see [below](#mcp-transport-streamable-http)):

| Type | API Endpoint | Description |
|---|---|---|
| **Local Sandbox** | `POST /local-sandbox` | A shared VM with multiple MCP servers (filesystem, terminal, git, excel, etc.). Has a unified `/data` workspace. Files can be uploaded/downloaded. |
| **Individual Sandbox** | `POST /sandbox/{server_name}` | A standalone MCP server instance for external services (github, woocommerce, snowflake, etc.). No shared filesystem. May return auth credentials. |

The runner automatically classifies each required server:

```python
# These servers run inside a Local Sandbox (shared VM)
LOCAL_SANDBOX_SERVERS = {
    "filesystem", "git", "terminal", "desktop-commander",
    "arxiv", "excel", "word", "powerpoint",
    "code-executor", "code-runner", "pdf-tools",
    "google_cloud", "poste_email_toolathlon",
}

# Everything else → Individual Sandbox
```

### MCP Transport: Streamable HTTP

> **Important for implementers and coding agents:** All MCP servers returned by the Klavis Sandbox API use the **Streamable HTTP** transport (`MCPServerStreamableHttp` in the OpenAI Agents SDK).

This means:

- **Every tool call is a stateless HTTP request.** Each `tools/list` or `tools/call` is an independent HTTP POST to the server URL — similar to a REST API call. There is **no persistent connection** or long-lived session between calls.
- **No keep-alive or SSE streaming session is needed.** You do not need to maintain a WebSocket, hold open an SSE connection, or implement reconnection logic. Simply send a request and receive a response.
- **No session state on the transport layer.** The server URL you receive from Klavis is self-contained. You can call it from any HTTP client at any time during the sandbox's lifetime.

**Sample usage with the MCP Python SDK — each snippet is a standalone, stateless call:**

```python
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

# Each call opens a short-lived HTTP request — no persistent connection needed
async with streamable_http_client(mcp_url) as (r, w, _):
    async with ClientSession(r, w) as session:
        await session.initialize()
        tools = await session.list_tools()   # or call tool
```

**Email MCP server — passing credentials via custom header:**

The email server requires an `x-email-config` header (base64-encoded JSON with `email`, `password`, `name`). Pass it via a pre-configured `httpx.AsyncClient`:

```python
import base64, json, httpx

email_cfg = {"email": "user@mcp.com", "password": "secret", "name": "User Name"}
headers = {"x-email-config": base64.b64encode(json.dumps(email_cfg).encode()).decode()}
http_client = httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120))

async with streamable_http_client(mcp_url, http_client=http_client) as (r, w, _):
    async with ClientSession(r, w) as session:
        await session.initialize()
        result = await session.call_tool("check_connection", {})
```

> **Note:** `auth_data` from the sandbox acquire response only contains connection info (IP, SMTP/IMAP ports) — the email credentials above are user-specified.

---

### Server Name Mappings

Some task-defined server names differ from the Klavis API names. Two mapping dicts handle this:

| Dict | Purpose | Example |
|---|---|---|
| `TASK_TO_LOCAL_SANDBOX_NAME` | Task server name → Klavis local sandbox name | `"pptx"` → `"powerpoint"` |
| `TASK_SERVER_TO_SANDBOX_NAME` | Task server name → Klavis individual sandbox name | `"google_sheet"` → `"google_sheets"` |

---

## Credential Injection & Network/File Hijacking

> **This section is critical for understanding how the runner works.** Without proper credential injection, preprocess and evaluation scripts cannot authenticate to external services (email, GitHub, Google Sheets, WooCommerce, Snowflake, etc.). The system uses **three distinct strategies** depending on what the service expects.

### Why This Is Needed

Toolathlon tasks were originally designed for a monolithic environment where:
- **Email scripts** connect to `localhost:1143` (IMAP) and `localhost:1587` (SMTP) — hardcoded addresses.
- **Google Sheets/Forms scripts** read credentials from `configs/google_credentials.json` — a hardcoded file path.
- **GCP scripts** read service-account keys from `configs/gcp-service_account.keys.json` — another hardcoded file path.
- **GitHub/WooCommerce/Snowflake scripts** read tokens via `from token_key_session import all_token_key_session` — which reads from env vars.

In the Klavis sandbox setup, each service runs **remotely** with **dynamically assigned** addresses and credentials. The runner must bridge this gap **without modifying the original task scripts**. It does this through three injection strategies:

### The Three Credential Injection Strategies

| Strategy | What it solves | Mechanism | Example servers |
|---|---|---|---|
| **1. Env vars** | Scripts read tokens/keys from `os.environ` | Set `KLAVIS_*` env vars before launching subprocess | github, woocommerce, snowflake |
| **2. Network hijack** | Scripts connect to hardcoded `localhost` ports | Monkeypatch `socket.getaddrinfo()` to redirect to remote IPs | email (IMAP/SMTP) |
| **3. File hijack** | Scripts read credentials from hardcoded file paths | Monkeypatch `builtins.open()` / `os.stat()` to redirect to temp files | google_sheets, google_forms, google_cloud |

### Strategy 1: Environment Variables (Direct)

**When used:** For services where the task's preprocess/eval scripts read credentials via `os.environ.get("KLAVIS_*")` or via `configs/token_key_session.py` (which itself reads from env vars).

**How it works:**

1. The runner calls `KlavisSandbox.acquire()` for a server (e.g., `woocommerce`).
2. The Klavis API returns `auth_data` containing keys/tokens.
3. `_apply_sandbox_auth()` maps each `auth_data` field to a `KLAVIS_*` env var using `SANDBOX_AUTH_ENV_MAPPING`:

```python
SANDBOX_AUTH_ENV_MAPPING = {
    "woocommerce": {
        "consumer_key":    "KLAVIS_WOOCOMMERCE_CONSUMER_KEY",
        "consumer_secret": "KLAVIS_WOOCOMMERCE_CONSUMER_SECRET",
        "site_url":        "KLAVIS_WOOCOMMERCE_SITE_URL",
        "admin_username":  "KLAVIS_WOOCOMMERCE_ADMIN_USERNAME",
        "admin_password":  "KLAVIS_WOOCOMMERCE_ADMIN_PASSWORD",
    },
    "github": {
        "access_token": "KLAVIS_GITHUB_TOKEN",
    },
    "snowflake": {
        "SNOWFLAKE_ACCOUNT":   "KLAVIS_SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_WAREHOUSE": "KLAVIS_SNOWFLAKE_WAREHOUSE",
        # ... (all Snowflake fields)
    },
}
```

4. These env vars are stored in `klavis.auth_env` and passed to subprocesses via `_build_subprocess_env()`.
5. Task-level `token_key_session.py` (or `configs/token_key_session.py`) reads them:

```python
# configs/token_key_session.py
all_token_key_session = Dict(
    github_token=os.environ.get("KLAVIS_GITHUB_TOKEN", ""),
    # ...
)
```

**Special case — Snowflake private key:** The Snowflake private key is a multi-line PEM string. It is written to a temp file, and `KLAVIS_SNOWFLAKE_PRIVATE_KEY_PATH` is set to point to that file. This is still env-var-based (no hijack needed) — the scripts read the path from the env var.

**No hijack is involved.** The `_hijack/sitecustomize.py` module is **not activated** for these servers.

### Strategy 2: Network Hijack (Socket Monkeypatch)

**When used:** For the **email server** (`poste_email_toolathlon`), where task scripts hardcode `localhost:1143` for IMAP and `localhost:1587` for SMTP.

**The problem:** The email MCP server runs remotely in the Klavis cloud. Its `auth_data` returns the real IMAP/SMTP server IPs and ports. But preprocess/eval scripts connect to `localhost:1143`/`localhost:1587` — hardcoded, not configurable.

**How it works:**

1. When acquiring the local sandbox, the runner extracts email `auth_data`:
   ```python
   # From acquire_for_servers():
   if sname == "poste_email_toolathlon":
       auth = server.get("auth_data") or {}
       self.auth_env["HIJACK_IMAP_HOST"] = str(auth["imap_server"])
       self.auth_env["HIJACK_IMAP_PORT"] = str(auth.get("imap_port", 1143))
       self.auth_env["HIJACK_SMTP_HOST"] = str(auth["smtp_server"])
       self.auth_env["HIJACK_SMTP_PORT"] = str(auth.get("smtp_port", 1587))
   ```

2. `_build_subprocess_env()` detects `HIJACK_IMAP_HOST` or `HIJACK_SMTP_HOST` in the env → prepends `_hijack/` to `PYTHONPATH`.

3. Python auto-imports `_hijack/sitecustomize.py` at subprocess startup (Python's built-in [sitecustomize mechanism](https://docs.python.org/3/library/site.html)).

4. `sitecustomize.py` patches `socket.getaddrinfo()`:
   ```python
   _REDIRECT_MAP = {
       1143: ("HIJACK_IMAP_HOST", "HIJACK_IMAP_PORT"),   # IMAP
       1587: ("HIJACK_SMTP_HOST", "HIJACK_SMTP_PORT"),   # SMTP
   }

   def _hijacked_getaddrinfo(host, port, ...):
       if host in {"localhost", "127.0.0.1", "::1"} and port in _REDIRECT_MAP:
           new_host = os.environ.get(host_env)
           new_port = os.environ.get(port_env)
           if new_host and new_port:
               host, port = new_host, int(new_port)
       return _orig_getaddrinfo(host, port, ...)
   ```

5. When the task script calls `imaplib.IMAP4("localhost", 1143)`, Python internally calls `socket.getaddrinfo("localhost", 1143)` → the patch intercepts it and resolves to the real remote IP:port instead.

**Result:** The task script thinks it's connecting to `localhost:1143`, but actually connects to the Klavis email server. No script modification needed.

### Strategy 3: File Hijack (open/stat Monkeypatch)

**When used:** For **Google Sheets**, **Google Forms**, and **Google Cloud (GCP)**, where task scripts read credentials from hardcoded file paths.

**The problem:**
- Google Sheets/Forms scripts open `configs/google_credentials.json` to read OAuth tokens.
- GCP scripts open `configs/gcp-service_account.keys.json` to read service-account keys.

These files don't exist locally — the credentials come dynamically from Klavis `auth_data`.

**How it works:**

1. The runner writes credentials to a **temp file**:
   ```python
   # For Google Sheets/Forms (OAuth credentials):
   tf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
   json.dump(creds, tf)    # {token, refresh_token, client_id, client_secret, ...}
   self.auth_env["HIJACK_GOOGLE_CREDENTIALS_PATH"] = tf.name

   # For GCP (service-account key):
   tf = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json")
   json.dump(auth, tf)     # Full GCP service-account JSON
   self.auth_env["HIJACK_GCP_SERVICE_ACCOUNT_PATH"] = tf.name
   ```

2. `_build_subprocess_env()` detects `HIJACK_GOOGLE_CREDENTIALS_PATH` or `HIJACK_GCP_SERVICE_ACCOUNT_PATH` → prepends `_hijack/` to `PYTHONPATH`.

3. `sitecustomize.py` patches `builtins.open()`, `io.open()`, `os.stat()`, and `pathlib.Path.stat()`:
   ```python
   _FILE_REDIRECT_SUFFIXES = {
       "configs/google_credentials.json": "HIJACK_GOOGLE_CREDENTIALS_PATH",
       "configs/gcp-service_account.keys.json": "HIJACK_GCP_SERVICE_ACCOUNT_PATH",
   }

   def _hijacked_open(file, *args, **kwargs):
       for suffix, env_var in _FILE_REDIRECT_SUFFIXES.items():
           if str(file).endswith(suffix):
               file = os.environ.get(env_var)  # redirect to temp file
       return _orig_open(file, *args, **kwargs)
   ```

4. When a task script calls `open("configs/google_credentials.json")`, the patch intercepts it and opens the temp file containing the real credentials instead. The `os.stat` / `Path.stat` patches ensure `Path.exists()` checks also succeed.

**Result:** The task script reads its hardcoded credential path and gets real Klavis credentials. No script modification needed.

### How `_build_subprocess_env` Ties It Together

All three strategies converge in `_build_subprocess_env()`, which builds the environment dict for child processes:

```python
def _build_subprocess_env(auth_env=None):
    env = os.environ.copy()
    pythonpath_parts = [str(PROJECT_ROOT)]

    if auth_env:
        env.update(auth_env)    # Inject all KLAVIS_* and HIJACK_* vars

    # If any HIJACK_* vars are present, prepend _hijack/ to PYTHONPATH
    # so sitecustomize.py is auto-loaded and applies monkeypatches
    if (env.get("HIJACK_IMAP_HOST")
            or env.get("HIJACK_SMTP_HOST")
            or env.get("HIJACK_GOOGLE_CREDENTIALS_PATH")
            or env.get("HIJACK_GCP_SERVICE_ACCOUNT_PATH")):
        pythonpath_parts.insert(0, SOCKET_HIJACK_DIR)  # _hijack/ directory

    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env
```

Key points:
- **HIJACK_\* vars absent** → `_hijack/sitecustomize.py` is **never loaded**; no monkeypatching occurs. Only `KLAVIS_*` env vars are used.
- **HIJACK_\* vars present** → `_hijack/` is prepended to `PYTHONPATH`, so Python auto-imports `sitecustomize.py` at startup, activating the relevant patches.
- Each subprocess gets its **own env** → parallel sandbox sessions won't conflict.

### Implementing This Yourself

If you are building your own Toolathlon runner (or adapting this code), here is what you need:

1. **For env-var-based auth** (github, woocommerce, snowflake):
   - Acquire the sandbox, read `auth_data`, store values as `KLAVIS_*` env vars.
   - Pass them to subprocess environments when running preprocess/eval scripts.
   - Ensure `configs/token_key_session.py` reads from `os.environ.get("KLAVIS_*")`.

2. **For network hijack** (email):
   - Store the remote IMAP/SMTP host:port from `auth_data` as `HIJACK_IMAP_HOST`, `HIJACK_IMAP_PORT`, `HIJACK_SMTP_HOST`, `HIJACK_SMTP_PORT`.
   - Include `_hijack/` in `PYTHONPATH` for the subprocess.
   - The `_hijack/sitecustomize.py` module will auto-patch `socket.getaddrinfo()`.

3. **For file hijack** (Google Sheets/Forms/Cloud):
   - Write the `auth_data` JSON to a temp file.
   - Set `HIJACK_GOOGLE_CREDENTIALS_PATH` or `HIJACK_GCP_SERVICE_ACCOUNT_PATH` to the temp file path.
   - Include `_hijack/` in `PYTHONPATH` for the subprocess.
   - The `_hijack/sitecustomize.py` module will auto-patch `open()`, `os.stat()`, and `pathlib.Path.stat()`.
   - **Clean up** temp files after the task completes (`cleanup_temp_files()`).

> **Note:** Strategies 2 and 3 only affect **local subprocess scripts** (preprocess, evaluation). The **agent's MCP tool calls** go directly to Klavis server URLs over HTTP and don't need hijacking — credentials for those are handled by the Klavis sandbox infrastructure itself.

---

## Project Structure

```
Toolathlon-mvp/
├── toolathlon_task_run_example.py   # Main entry point — the complete runner
├── requirements.txt                 # Python dependencies
├── task_status_in_klavis_sandbox.md # Task support status reference
├── .env                             # Your API keys (create this)
├── _hijack/                         # ⚡ Network & file-open hijack module
│   └── sitecustomize.py             #   Auto-loaded via PYTHONPATH; patches
│                                    #   socket.getaddrinfo() and builtins.open()
│                                    #   to redirect hardcoded localhost/file paths
│                                    #   to Klavis sandbox endpoints. See:
│                                    #   "Credential Injection & Network/File Hijacking"
├── configs/
│   └── token_key_session.py         # Reads KLAVIS_* env vars → all_token_key_session dict
├── tasks/
│   └── finalpool/                   # All 108 Toolathlon benchmark tasks
│       ├── arrange-workspace/
│       ├── courses-ta-hws/
│       ├── inventory-sync/
│       └── ...
└── utils/                           # Shared utilities
    ├── general/helper.py            # normalize_str, read_json, write_json, etc.
    ├── app_specific/github/         # GitHub API helpers (used by preprocess/eval)
    ├── app_specific/huggingface/    # HuggingFace dataset helpers
    └── data_processing/process_ops.py  # File copy/duplication utilities
```