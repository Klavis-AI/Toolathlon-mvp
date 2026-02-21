# Sandbox API Reference

Base URL: `https://api.klavis.ai`

All endpoints require Bearer token authentication via the `Authorization` header.

---

## Sandbox

### 1. POST `/sandbox/{server_name}` — Acquire a sandbox

Acquire an idle sandbox instance for a specific MCP server. The sandbox will be marked as 'occupied'. Optionally choose a benchmark (e.g., 'MCP_Atlas', 'Toolathlon') to configure the sandbox. The benchmark parameter may affect BOTH (1) the initial data environment and (2) the MCP server implementation itself. You may also specify a `test_account_email` to acquire a specific test account.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `server_name` | `SandboxMCPServer` | Yes | The MCP server name |

**Request Body:** `AcquireSandboxRequest`

```json
{
  "benchmark": "MCP_Atlas" | "Toolathlon" | null,
  "test_account_email": "string" | null,
  "tags": { "key": "value" } | null
}
```

**Response (201):** `CreateSandboxResponse`

```json
{
  "sandbox_id": "string",
  "server_urls": { "server_name": "url" } | null,
  "server_name": "SandboxMCPServer",
  "status": "idle" | "occupied" | "error",
  "message": "string"
}
```

---

### 2. GET `/sandbox/{server_name}/{sandbox_id}` — Get sandbox details

Retrieve detailed information about a specific sandbox instance.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `server_name` | `SandboxMCPServer` | Yes | The MCP server name |
| `sandbox_id` | `string` | Yes | The unique sandbox identifier |

**Response (200):** `SandboxInfo`

```json
{
  "sandbox_id": "string",
  "server_url": "string" | null,
  "server_name": "SandboxMCPServer",
  "status": "idle" | "occupied" | "error",
  "benchmark": "string" | null,
  "updated_at": "datetime" | null,
  "metadata": { } | null,
  "auth_data": { } | null,
  "tags": { } | null
}
```

---

### 3. GET `/sandbox` — List all sandboxes

Get all sandboxes associated with the API key's account. Optionally filter by tags.

**Query Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `tags` | `string` \| `null` | No | Optional JSON string of tags to filter by (e.g., `'{"env": "prod"}'`) |

**Response (200):** `ListSandboxesResponse`

```json
{
  "sandboxes": [
    {
      "sandbox_id": "string",
      "server_name": "string",
      "status": "idle" | "occupied" | "error",
      "benchmark": "string" | null,
      "tags": { } | null,
      "updated_at": "datetime" | null
    }
  ],
  "total_count": 0
}
```

---

### 4. DELETE `/sandbox/{server_name}/{sandbox_id}` — Release sandbox

Release an occupied sandbox back to idle state and marks the sandbox as available for reuse.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `server_name` | `SandboxMCPServer` | Yes | The MCP server name |
| `sandbox_id` | `string` | Yes | The unique sandbox identifier |

**Response (200):** `ReleaseSandboxResponse`

```json
{
  "sandbox_id": "string",
  "status": "idle" | "occupied" | "error",
  "message": "string"
}
```

---

### 5. POST `/sandbox/{server_name}/{sandbox_id}/reset` — Reset sandbox to initial state

Reset the sandbox to its initial empty state, clearing all data while maintaining the sandbox instance.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `server_name` | `SandboxMCPServer` | Yes | The MCP server name |
| `sandbox_id` | `string` | Yes | The unique sandbox identifier |

**Response (200):** `ResetSandboxResponse`

```json
{
  "sandbox_id": "string",
  "status": "idle" | "occupied" | "error",
  "message": "string"
}
```

---

## Local Sandbox

### 6. POST `/local-sandbox` — Acquire a local sandbox

Initializes a specialized Virtual Machine environment (Local Sandbox) that hosts multiple interconnected MCP servers. Optionally specify a benchmark (e.g., 'Toolathlon') to configure the sandbox. The benchmark parameter may affect BOTH (1) the initial data environment and (2) the MCP server implementation itself.

**Request Body (required):** `AcquireLocalSandboxRequest`

```json
{
  "server_names": ["filesystem", "git", "terminal", ...] | "ALL",
  "benchmark": "MCP_Atlas" | "Toolathlon" | null,
  "test_account_email": "string" | null
}
```

**Response (201):** `AcquireLocalSandboxResponse`

```json
{
  "local_sandbox_id": "string",
  "status": "idle" | "occupied" | "error" | null,
  "benchmark": "string" | null,
  "servers": [
    {
      "server_name": "string" | null,
      "id": "string",
      "mcp_server_url": "string" | null,
      "status": "idle" | "occupied" | "error" | null,
      "benchmark": "string" | null,
      "updated_at": "string" | null,
      "metadata": { } | null
    }
  ],
  "message": "string" | null
}
```

---

### 7. GET `/local-sandbox/{local_sandbox_id}` — Get local sandbox details

Retrieves details about a local sandbox environment, including its status and all running servers.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | The ID of the local sandbox to retrieve |

**Response (200):** `LocalSandboxInfo`

```json
{
  "local_sandbox_id": "string",
  "created_at": "string",
  "status": "idle" | "occupied" | "error" | null,
  "benchmark": "string" | null,
  "servers": [
    {
      "server_name": "string" | null,
      "id": "string",
      "mcp_server_url": "string" | null,
      "status": "idle" | "occupied" | "error" | null,
      "benchmark": "string" | null,
      "updated_at": "string" | null,
      "metadata": { } | null
    }
  ]
}
```

---

### 8. GET `/local-sandbox` — List local sandboxes

Lists all active local sandbox environments owned by the user.

**Response (200):** `ListLocalSandboxesResponse`

```json
{
  "local_sandboxes": [ LocalSandboxInfo, ... ],
  "total_count": 0
}
```

---

### 9. DELETE `/local-sandbox/{local_sandbox_id}` — Release a local sandbox

Releases the local sandbox VM and all associated servers, cleaning up the shared environment.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | The ID of the local sandbox to release |

**Response (200):** `{}`

---

### 10. POST `/local-sandbox/{local_sandbox_id}/reset` — Reset local sandbox to initial state

Resets the state of the local sandbox VM and all its servers to their initial state.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | The ID of the local sandbox to reset |

**Response (200):** `{}`

---

### 11. POST `/local-sandbox/{local_sandbox_id}/upload-url` — Get URL to upload your data

Generates a signed URL to upload a `tar.gz` archive containing your workspace files. Once uploaded, use the `/initialize` endpoint to unpack it into the sandbox.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | The local sandbox identifier |

**Response (200):** `UploadUrlResponse`

```json
{
  "upload_url": "string",
  "expires_in_minutes": 0
}
```

---

### 12. POST `/local-sandbox/{local_sandbox_id}/initialize` — Initialize sandbox from your uploaded data

Extracts the uploaded `tar.gz` archive into the sandbox workspace. This must be called after successfully uploading the file using the URL from `/upload-url`.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | The local sandbox identifier |

**Response (200):** `InitializeSandboxResponse`

```json
{
  "sandbox_id": "string",
  "status": "idle" | "occupied" | "error",
  "message": "string"
}
```

---

### 13. GET `/local-sandbox/{local_sandbox_id}/dump` — Download sandbox data

Creates a `tar.gz` archive of the current workspace and provides a temporary download URL. Useful for saving your work or exporting the sandbox state.

**Path Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | The local sandbox identifier |

**Response (200):** `DumpUrlResponse`

```json
{
  "download_url": "string",
  "expires_in_minutes": 0
}
```

---

## Components / Schemas

### SandboxMCPServer

Supported MCP servers for sandboxing.

**Type:** `string` (enum)

**Values:** `jira`, `github`, `salesforce`, `hubspot`, `notion`, `airtable`, `linear`, `asana`, `google_sheets`, `google_drive`, `google_docs`, `gmail`, `google_calendar`, `google_forms`, `clickup`, `close`, `monday`, `motion`, `onedrive`, `microsoft_teams`, `outlook_mail`, `cal.com`, `quickbooks`, `moneybird`, `dropbox`, `shopify`, `woocommerce`, `outlook_calendar`, `resend`, `wordpress`, `mem0`, `supabase`, `slack`, `confluence`, `discord`, `snowflake`, `postgres`, `mongodb`, `youtube`, `googleworkspaceatlas`, `arxiv_latex`, `calculator`, `clinicaltrialsgov`, `met_museum`, `open_library`, `osm`, `pubmed`, `us_weather`, `whois`, `wikipedia`, `weather`, `twelvedata`, `national_parks`, `lara_translate`, `e2b`, `context7`, `alchemy`, `weights_and_biases`, `huggingface`

---

### LocalSandboxMCPServer

Supported MCP servers for local sandboxing (typically stateless or local-only servers).

**Type:** `string` (enum)

**Values:** `filesystem`, `git`, `terminal`, `desktop-commander`, `arxiv`, `excel`, `word`, `powerpoint`, `code-executor`, `code-runner`, `pdf-tools`, `google_cloud`, `poste_email_toolathlon`, `localmemory`

---

### BenchmarkEnum

Supported benchmarks for sandbox initial environment.

**Type:** `string` (enum)

**Values:** `MCP_Atlas`, `Toolathlon`

---

### SandboxStatus

Status of a sandbox instance.

**Type:** `string` (enum)

**Values:** `idle`, `occupied`, `error`

---

### AcquireSandboxRequest

Request model for acquiring a sandbox.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `benchmark` | `BenchmarkEnum` \| `null` | No | Optional benchmark to configure the sandbox. May affect initial data and MCP server implementation. |
| `test_account_email` | `string` \| `null` | No | Optional email of a specific test account to acquire. |
| `tags` | `object` \| `null` | No | Optional custom tags to associate with the sandbox. |

---

### CreateSandboxResponse

Response model for sandbox acquisition.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | `string` | Yes | Unique identifier for the acquired sandbox |
| `server_urls` | `object` \| `null` | No | MCP server URLs keyed by server name |
| `server_name` | `SandboxMCPServer` | Yes | The MCP server name |
| `status` | `SandboxStatus` | Yes | Current status of the sandbox |
| `message` | `string` | Yes | Status message |

---

### SandboxInfo

Detailed information about a sandbox.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | `string` | Yes | Unique identifier for the sandbox |
| `server_url` | `string` \| `null` | No | URL to connect to the MCP server |
| `server_name` | `SandboxMCPServer` | Yes | The MCP server type |
| `status` | `SandboxStatus` | Yes | Current status of the sandbox |
| `benchmark` | `string` \| `null` | No | Benchmark for the sandbox initial environment |
| `updated_at` | `datetime` \| `null` | No | Last update timestamp |
| `metadata` | `object` \| `null` | No | Additional metadata for the sandbox |
| `auth_data` | `object` \| `null` | No | Authentication data for the sandbox |
| `tags` | `object` \| `null` | No | Custom tags for the sandbox |

---

### SandboxListItem

Individual sandbox item in list response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | `string` | Yes | Unique identifier for the sandbox |
| `server_name` | `string` | Yes | The MCP server name |
| `status` | `SandboxStatus` | Yes | Current status of the sandbox |
| `benchmark` | `string` \| `null` | No | Benchmark for the sandbox initial environment |
| `tags` | `object` \| `null` | No | Custom tags for the sandbox |
| `updated_at` | `datetime` \| `null` | No | Last update timestamp |

---

### ListSandboxesResponse

Response model for listing all sandboxes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandboxes` | `SandboxListItem[]` | Yes | List of sandboxes |
| `total_count` | `integer` | Yes | Total number of sandboxes |

---

### ReleaseSandboxResponse

Response model for sandbox release.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | `string` | Yes | Released sandbox identifier |
| `status` | `SandboxStatus` | Yes | Current status after release (should be idle) |
| `message` | `string` | Yes | Release confirmation message |

---

### ResetSandboxResponse

Response model for sandbox reset.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | `string` | Yes | Sandbox identifier |
| `status` | `SandboxStatus` | Yes | Current status after reset |
| `message` | `string` | Yes | Reset result message |

---

### AcquireLocalSandboxRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `server_names` | `LocalSandboxMCPServer[]` \| `"ALL"` | Yes | List of MCP servers to acquire, or `"ALL"` for all available local servers |
| `benchmark` | `BenchmarkEnum` \| `null` | No | Optional benchmark to configure the local sandbox. |
| `test_account_email` | `string` \| `null` | No | Specific test account email |

---

### AcquireLocalSandboxResponse

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | Unique identifier for the entire local sandbox environment |
| `status` | `SandboxStatus` \| `null` | No | Overall status of the local sandbox environment |
| `benchmark` | `string` \| `null` | No | Benchmark environment configuration used for the local sandbox |
| `servers` | `LocalSandboxServerItem[]` | Yes | List of interconnected MCP servers running in this sandbox |
| `message` | `string` \| `null` | No | Status message |

---

### LocalSandboxInfo

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `local_sandbox_id` | `string` | Yes | Unique identifier for the local sandbox environment |
| `created_at` | `string` | Yes | Timestamp when the sandbox was created |
| `status` | `SandboxStatus` \| `null` | No | Current status of the local sandbox environment |
| `benchmark` | `string` \| `null` | No | Benchmark environment configuration for the local sandbox |
| `servers` | `LocalSandboxServerItem[]` | Yes | List of MCP servers in this sandbox |

---

### LocalSandboxServerItem

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `server_name` | `string` \| `null` | No | Name of the MCP server |
| `id` | `string` | Yes | Unique identifier for this specific server instance within the sandbox |
| `mcp_server_url` | `string` \| `null` | No | URL to connect to this specific MCP server instance |
| `status` | `SandboxStatus` \| `null` | No | Current status of this server's sandbox |
| `benchmark` | `string` \| `null` | No | Benchmark environment configuration |
| `updated_at` | `string` \| `null` | No | Last update timestamp |
| `metadata` | `object` \| `null` | No | Additional metadata |

---

### ListLocalSandboxesResponse

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `local_sandboxes` | `LocalSandboxInfo[]` | Yes | List of all local sandbox environments |
| `total_count` | `integer` | Yes | Total number of local sandboxes |

---

### UploadUrlResponse

Response for the upload URL endpoint.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `upload_url` | `string` | Yes | Signed GCS URL to PUT the tar.gz archive to |
| `expires_in_minutes` | `integer` | Yes | Minutes until the upload URL expires |

---

### InitializeSandboxResponse

Response model for sandbox initialization.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sandbox_id` | `string` | Yes | Sandbox identifier |
| `status` | `SandboxStatus` | Yes | Current status |
| `message` | `string` | Yes | Initialization result message |

---

### DumpUrlResponse

Response for the dump endpoint — returns a signed download URL.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `download_url` | `string` | Yes | Signed GCS URL to GET the tar.gz archive from |
| `expires_in_minutes` | `integer` | Yes | Minutes until the download URL expires |

---

### MemoryUploadUrlResponse

Response for the memory upload URL endpoint.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `upload_url` | `string` | Yes | Signed GCS URL to PUT the memory JSONL file to |
| `expires_in_minutes` | `integer` | Yes | Minutes until the upload URL expires |

---

### HTTPValidationError

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `detail` | `ValidationError[]` | No | List of validation errors |

---

### ValidationError

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `loc` | `(string \| integer)[]` | Yes | Location of the error |
| `msg` | `string` | Yes | Error message |
| `type` | `string` | Yes | Error type |
| `input` | `any` | No | Input that caused the error |
| `ctx` | `object` | No | Error context |
