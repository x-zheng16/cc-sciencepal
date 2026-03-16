# SciencePal REST API Reference

Base URL: `$SCIENCEPAL_BASE_URL` (default `https://sciencepal.ai/api`).
Auth: `Authorization: Bearer $SCIENCEPAL_ACCESS_TOKEN`.

## Agent Runs

### POST `/agent/initiate` -- Start a new run

**Format: form-data (NOT JSON).**

| Field               | Required | Default | Description              |
| ------------------- | -------- | ------- | ------------------------ |
| `prompt`            | yes      |         | Task prompt              |
| `agent_select_type` | no       | `auto`  | `auto` or `manual`       |
| `agent_id`          | no       |         | Specific agent ID        |
| `web_search_on`     | no       | `true`  | Enable web search        |

Response: `{ "thread_id": "...", "agent_run_id": "..." }`

### GET `/agent-run/{agent_run_id}` -- Check run status

Response: `{ "id", "threadId", "status", "startedAt", "completedAt", "error" }`

Status values: `running`, `completed`, `failed`, `stopped`.

### POST `/agent-run/{agent_run_id}/stop` -- Stop a run

### GET `/agent-run/{agent_run_id}/stream` -- SSE event stream

Query param: `?token=<access_token>`.

### GET `/thread/{thread_id}/agent-runs` -- List all runs for a thread

Response: `{ "agent_runs": [{ "id", "thread_id", "status", "started_at", "completed_at", "responses", "error" }] }`

## Sandbox

### GET `/thread/{thread_id}/sandbox` -- Get sandbox info

Response: `{ "thread_id", "project_id", "sandbox_id", "sandbox_info": { "vnc_preview", "sandbox_url" } }`

### GET `/sandboxes/{sandbox_id}/files?path=<path>` -- List files

Response: `{ "files": [{ "name", "path", "is_dir", "size", "mod_time", "permissions" }] }`

### GET `/sandboxes/{sandbox_id}/files/content?path=<path>` -- Read file content

Returns raw bytes with `Content-Disposition: attachment`.

### POST `/sandboxes/{sandbox_id}/files` -- Upload file

**Format: form-data.**

| Field  | Type | Description              |
| ------ | ---- | ------------------------ |
| `path` | text | Destination path         |
| `file` | file | File content             |

Response: `{ "status": "success", "created": true, "path": "..." }`

### DELETE `/sandboxes/{sandbox_id}/files?path=<path>` -- Delete file

Response: `{ "status": "success", "deleted": true, "path": "..." }`

### POST `/project/{project_id}/sandbox/ensure-active` -- Wake up sandbox

Call this before any sandbox operations if the run completed more than 10 minutes ago.

Response: `{ "status": "success", "sandbox_id": "...", "message": "Sandbox is active" }`
