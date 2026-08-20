# SciencePal REST API Reference

Base URL, per environment: `$SCIENCEPAL_STG_BASE_URL` (default `https://stg.sciencepal.ai/api`) or
`$SCIENCEPAL_PRD_BASE_URL` (default `https://sciencepal.ai/api`).
Auth: `Authorization: Bearer $SCIENCEPAL_STG_ACCESS_TOKEN` or `$SCIENCEPAL_PRD_ACCESS_TOKEN`
(legacy `$SCIENCEPAL_ACCESS_TOKEN` still works as a prd fallback).

One group below is the exception: `## Follow-up Message Insert` targets Supabase, not this base URL,
and uses a second credential.

## Agent Runs

### POST `/agent/initiate` -- Start a new run

**Format: form-data (NOT JSON).** A JSON body is rejected with `422`.

| Field               | Required | Default | Description              |
| ------------------- | -------- | ------- | ------------------------ |
| `prompt`            | yes      |         | Task prompt              |
| `agent_select_type` | no       | `auto`  | `auto` or `manual`       |
| `agent_id`          | no       |         | Specific agent ID        |
| `web_search_on`     | no       | `true`  | Enable web search        |

Response: `{ "thread_id": "...", "agent_run_id": "..." }`

**Slow, and not idempotent.** This call provisions a sandbox before responding, so it routinely
exceeds a 60s client timeout while succeeding server-side. A client timeout is NOT a failure: the
session exists and the run is live, but the caller never received the two IDs. Recover by listing
sessions, never by retrying, since a retry starts a second run.

There is no request-deduplication key. Measured 2026-08-20 on staging: two calls carrying an
identical `idempotency_key` form field, each timing out client-side, took the account from 156 to
157 to 158 sessions. The field is accepted and ignored, so sending one does not make a retry safe.

### GET `/agent-run/{agent_run_id}` -- Check run status

Response: `{ "id", "threadId", "status", "startedAt", "completedAt", "error" }`

Status values: `running`, `completed`, `failed`, `stopped`.

### POST `/agent-run/{agent_run_id}/stop` -- Stop a run

### POST `/thread/{thread_id}/agent/start` -- Re-start the agent on an existing thread

Second leg of the follow-up flow: insert the user message first (see `## Follow-up Message Insert`),
then call this to run the agent over the updated thread.

**Format: JSON.** Body is an empty object `{}`; no fields are sent.

Response: a JSON object, passed through verbatim. No individual field is read, but the caller does
assign into it, so an object is required while its fields are not;
`/agent-run/{agent_run_id}` remains the way to poll the resulting run.

### GET `/agent-run/{agent_run_id}/stream` -- SSE event stream

Query param: `?token=<access_token>`.

### GET `/thread/{thread_id}/agent-runs` -- List all runs for a thread

Response: `{ "agent_runs": [{ "id", "thread_id", "status", "started_at", "completed_at", "responses", "error" }] }`

## Sessions

### GET `/projects/statuses` -- List the account's sessions and their statuses

| Query param | Required | Description                                  |
| ----------- | -------- | -------------------------------------------- |
| `since`     | no       | ISO8601; only sessions updated after this time |

Omit `since` entirely to list everything; it is the only parameter sent, and when it is absent no
query string is sent at all.

Response: `{ "statuses": [{ "project_id", "status" }] }`. Rows may carry more fields; only
`project_id` and `status` are read.

`status` values are OBSERVED, not an enumeration the server publishes, so treat the list as a floor
and expect values not on it. Measured 2026-08-20 across both environments, population = every row
returned for one account with no `since` filter, predicate = each row's `status`:

| Value          | stg (n=153) | prd (n=118) |
| -------------- | ----------- | ----------- |
| `completed`    | 139         | 94          |
| `stopped`      | 8           | 9           |
| `asked`        | 2           | 8           |
| `initializing` | 2           | 0           |
| `failed`       | 1           | 1           |
| `null`         | 1           | 6           |

`null` is a value the endpoint really returns, not a missing key; what it denotes is not
determinable from the client, so do not treat it as an error. Note that `initializing` appeared only
in the staging sample, which is a sampling artifact rather than an environment difference: it is a
transient state, and the counts above are one instant each.

A bare top-level array is tolerated as a fallback shape, but the object form above is what the
server sends.

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

## Follow-up Message Insert

First leg of the follow-up flow, and the one call in this file that does NOT go to the SciencePal
API base URL. It is a Supabase PostgREST insert, so both the host and the auth scheme differ:

- Host: `$SCIENCEPAL_STG_SUPABASE_URL` or `$SCIENCEPAL_PRD_SUPABASE_URL`, of the form
  `https://<project-ref>.supabase.co`. Each environment has its own project.
- Auth: TWO headers. `apikey: $SCIENCEPAL_STG_SUPABASE_ANON_KEY` (or the prd one) identifies the
  project; `Authorization: Bearer <access token>` is the SAME SciencePal access token used
  everywhere else in this file, and is what Row Level Security checks.

Row Level Security limits the insert to threads owned by the token's user. An insert aimed at
someone else's thread, or at a thread that lives in the other environment, is rejected by the
database rather than by the API.

### POST `/rest/v1/messages` -- Insert a user message into a thread

**Format: JSON.** Headers: `apikey`, `Authorization`, `Content-Type: application/json`,
`Prefer: return=minimal`.

| Field            | Type    | Value                                                          |
| ---------------- | ------- | -------------------------------------------------------------- |
| `thread_id`      | string  | Target thread                                                   |
| `type`           | string  | `user`                                                          |
| `is_llm_message` | boolean | `true`                                                          |
| `content`        | string  | JSON **string**, not an object: `{"role":"user","content":...}` |
| `metadata`       | object  | `{}`                                                            |

`content` is double-encoded on purpose: the row shape mirrors the web frontend, which stores the
message envelope as a serialized string.

Response: `200`, `201`, or `204` all mean success, and `Prefer: return=minimal` means the body is
normally empty. Any other status is a failure; `401` specifically means the access token is expired.

## Wire Gotchas

- `/agent/initiate` and `POST /sandboxes/{sandbox_id}/files` take form-data. Sending JSON to
  `/agent/initiate` returns `422`. Every other write in this file is JSON.
- The two follow-up legs must run in order: insert the message, then start the agent. Starting
  first runs the agent over the thread as it was.
- A `401` on the Supabase insert leg, from a token the SciencePal API just accepted, means the
  token is time-expired. The backend API tolerates an expired JWT; Supabase does not. Refresh the
  access token rather than hunting for a Supabase-specific problem.
- A non-401 failure on the insert leg is usually Row Level Security: check that the thread belongs
  to the token's user and that the thread and the token are from the same environment.
- The sandbox stops after idling. Wake it with `/project/{project_id}/sandbox/ensure-active` before
  file operations on a run that finished a while ago.
