---
name: sciencepal
description: |
  Run SciencePal science research agents (material, bio, protein, plasma, patent).
  Use when the user wants to run a SciencePal task, check its status, or download results.
---

# SciencePal

Science research agent platform.
Agents: general, biology, material, protein, plasma, patent.

## API (reverse-engineered, no SDK needed)

Base URL: `$SCIENCEPAL_BASE_URL` (default `https://sciencepal.ai/api`).
Auth: `Authorization: Bearer $SCIENCEPAL_ACCESS_TOKEN`.

| Endpoint                                            | Method | Format    | Purpose              |
| --------------------------------------------------- | ------ | --------- | -------------------- |
| `/agent/initiate`                                   | POST   | form-data | Start a new run      |
| `/agent-run/{agent_run_id}`                         | GET    |           | Check run status     |
| `/agent-run/{agent_run_id}/stop`                    | POST   |           | Stop a run           |
| `/agent-run/{agent_run_id}/stream`                  | GET    |           | SSE event stream     |
| `/thread/{thread_id}/agent-runs`                    | GET    |           | List thread runs     |
| `/thread/{thread_id}/sandbox`                       | GET    |           | Get sandbox info     |
| `/sandboxes/{sandbox_id}/files?path=<path>`         | GET    |           | List files           |
| `/sandboxes/{sandbox_id}/files/content?path=<path>` | GET    |           | Read file content    |
| `/sandboxes/{sandbox_id}/files`                     | POST   | form-data | Upload file          |
| `/sandboxes/{sandbox_id}/files`                     | DELETE |           | Delete file          |
| `/project/{project_id}/sandbox/ensure-active`       | POST   |           | Wake up sandbox      |
| `/agents`                                           | GET    |           | List all agents      |

Status values: `running`, `completed`, `failed`, `stopped`.

## Scripts

All scripts: `uv run --project ~/.claude/cc-python python3 <script>`.
Working directory: this skill's `scripts/` folder.

1. **`start_run.py`** -- Start a run, print `thread_id` + `agent_run_id`.
2. **`poll_and_download.py`** -- Poll until complete, resolve sandbox from thread, download files.

## Workflow

```bash
# 1. Start
uv run --project ~/.claude/cc-python python3 scripts/start_run.py --prompt "user question"
# returns: {thread_id, agent_run_id}

# 2. Poll + download (foreground or background)
uv run --project ~/.claude/cc-python python3 scripts/poll_and_download.py \
  --agent-run-id <agent_run_id> \
  --thread-id <thread_id> \
  --output-dir ~/cc_tmp/sciencepal/<agent_run_id>/
```

## Rules

- Print `thread_id` and `agent_run_id` immediately after starting.
- Terminal statuses: `completed`, `failed`, `stopped`. Only download for `completed`.
- Output files go to `~/cc_tmp/sciencepal/<run_id>/`, not inside any project repo.
- `/agent/initiate` uses **form-data**, not JSON.
