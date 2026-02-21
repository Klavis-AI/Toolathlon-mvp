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
- [Execution Pipeline (Step by Step)](#execution-pipeline-step-by-step)
- [Key Concepts](#key-concepts)
  - [Klavis Sandbox Types](#klavis-sandbox-types)
  - [MCP Transport: Streamable HTTP](#mcp-transport-streamable-http)
  - [Server Name Mappings](#server-name-mappings)
  - [Authentication & Credentials](#authentication--credentials)

---

## How It Works

The runner automates the full lifecycle of a Toolathlon benchmark task:

1. **Load** the task definition (prompt, system prompt, required MCP servers) from disk.
2. **Acquire** remote sandbox environments from Klavis AI — each providing MCP tool servers (filesystem, terminal, git, etc.).
3. **Preprocess** — run any task-specific setup scripts to prepare the initial workspace.
4. **Upload** the initial workspace tarball to the remote sandbox.
5. **Run the agent** — an LLM-powered agent uses MCP tools via the sandbox to complete the task.
6. **Download** the resulting workspace from the sandbox.
7. **Evaluate** — run the task's evaluation script to check correctness (PASS/FAIL).
8. **Cleanup** — release all sandbox resources.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Your Machine (Local)                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │          toolathlon_task_run_example.py                    │  │
│  │                                                           │  │
│  │  1. load_task()          ─── reads task config & prompts  │  │
│  │  2. run_preprocess()     ─── optional setup script        │  │
│  │  3. KlavisSandbox        ─── acquires remote sandboxes    │  │
│  │  4. upload_workspace()   ─── sends tar.gz to sandbox      │  │
│  │  5. Agent + Runner       ─── LLM agent loop               │  │
│  │  6. download_workspace() ─── retrieves results            │  │
│  │  7. evaluate()           ─── runs eval scripts            │  │
│  └──────────┬──────────────────────┬─────────────────────────┘  │
│             │                      │                            │
│         LLM API calls         MCP tool calls                    │
│             │                      │                            │
└─────────────┼──────────────────────┼────────────────────────────┘
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

**Data flow during the agent loop:**

```
Agent (LLM)  ──tool call──▶  MCP Server (Klavis)  ──executes──▶  Sandbox Env
    ▲                              │
    └──────── tool result ─────────┘
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

## Execution Pipeline (Step by Step)

Below is the detailed sequence of what `run_task()` does:

```
  ┌──────────────┐
  │  load_task() │  Read task_config.json, task.md, agent_system_prompt.md
  └──────┬───────┘
         ▼
  ┌────────────────────────┐
  │ KlavisSandbox.acquire  │  Call Klavis API to provision sandbox environments
  │   _for_servers()       │  → Local sandbox (filesystem, terminal, etc.)
  └──────┬─────────────────┘  → Individual sandboxes (github, woocommerce, etc.)
         ▼
  ┌─────────────────────┐
  │  run_preprocess()   │  If preprocess/main.py exists:
  │                     │    1. Copy initial_workspace to temp dir
  │                     │    2. Run preprocess script
  │                     │    3. Re-pack as new tarball
  └──────┬──────────────┘
         ▼
  ┌──────────────────────────┐
  │ upload_workspace_tarball │  Upload tar.gz → Klavis signed URL → extract into /data
  └──────┬───────────────────┘
         ▼
  ┌─────────────────────────────────────────────┐
  │          Agent Loop (OpenAI Agents SDK)      │
  │                                              │
  │  Agent receives:                             │
  │    • system_prompt (from agent_system_prompt)│
  │    • input (from task.md)                    │
  │    • MCP tools (from Klavis sandbox servers) │
  │                                              │
  │  Runs up to max_turns tool-call rounds       │
  │  ToolLoggingHooks prints each call in        │
  │  real time                                   │
  └──────┬──────────────────────────────────────┘
         ▼
  ┌────────────────────────────┐
  │ download_and_print_        │  Download workspace tar.gz from sandbox
  │    workspace()             │  Extract to <task>/workspace/
  └──────┬─────────────────────┘
         ▼
  ┌──────────────┐
  │  evaluate()  │  Run check_local.py or evaluation/main.py
  │              │  Returns PASS ✓ or FAIL ✗
  └──────┬───────┘
         ▼
  ┌──────────────┐
  │  release_all │  Delete all sandbox instances (cleanup)
  └──────────────┘
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

---

### Server Name Mappings

Some task-defined server names differ from the Klavis API names. Two mapping dicts handle this:

| Dict | Purpose | Example |
|---|---|---|
| `TASK_TO_LOCAL_SANDBOX_NAME` | Task server name → Klavis local sandbox name | `"pptx"` → `"powerpoint"` |
| `TASK_SERVER_TO_SANDBOX_NAME` | Task server name → Klavis individual sandbox name | `"google_sheet"` → `"google_sheets"` |

### Authentication & Credentials

Some individual sandboxes (e.g., woocommerce, github, snowflake) return authentication credentials. These are automatically extracted and injected into environment variables via `SANDBOX_AUTH_ENV_MAPPING`:

```python
# Example: woocommerce sandbox returns these auth fields,
# which get stored as environment variables:
"woocommerce": {
    "consumer_key":    "KLAVIS_WOOCOMMERCE_CONSUMER_KEY",
    "consumer_secret": "KLAVIS_WOOCOMMERCE_CONSUMER_SECRET",
    "site_url":        "KLAVIS_WOOCOMMERCE_SITE_URL",
    ...
}
```

These env vars are passed to preprocess and evaluation scripts automatically.

---

## Project Structure

```
Toolathlon-mvp/
├── toolathlon_task_run_example.py   # Main entry point — the complete runner
├── requirements.txt                 # Python dependencies
├── task_status_in_klavis_sandbox.md # Task support status reference
├── .env                             # Your API keys (create this)
├── configs/                         # Token/key/session config helpers
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