---
name: sciencepal
description: |
  Run SciencePal science research agents (material, bio, protein, plasma, patent).
  Use when the user wants to run a SciencePal task, check its status, or manage sandbox files.
---

# SciencePal

Science research agent platform.
Agents: general, biology, material, protein, plasma, patent.

## API

Base URL: `$SCIENCEPAL_BASE_URL` (default `https://sciencepal.ai/api`).
Auth: `Authorization: Bearer $SCIENCEPAL_ACCESS_TOKEN`.

| Endpoint                                            | Method | Format    | Purpose             |
| --------------------------------------------------- | ------ | --------- | ------------------- |
| `/agent/initiate`                                   | POST   | form-data | Start a new run     |
| `/agent-run/{id}`                                   | GET    |           | Check run status    |
| `/agent-run/{id}/stop`                              | POST   |           | Stop a run          |
| `/agent-run/{id}/stream`                            | GET    |           | SSE event stream    |
| `/thread/{id}/agent-runs`                           | GET    |           | List thread runs    |
| `/thread/{id}/sandbox`                              | GET    |           | Get sandbox info    |
| `/sandboxes/{id}/files?path=`                       | GET    |           | List files          |
| `/sandboxes/{id}/files/content?path=`               | GET    |           | Read file content   |
| `/sandboxes/{id}/files`                             | POST   | form-data | Upload file         |
| `/sandboxes/{id}/files`                             | DELETE |           | Delete file         |
| `/project/{id}/sandbox/ensure-active`               | POST   |           | Wake up sandbox     |

Status values: `running`, `completed`, `failed`, `stopped`.

## Scripts

All scripts: `uv run --project ~/.claude/cc-python python3 <script>`.
Working directory: this skill's `scripts/` folder.

1. **`start.py`** -- Start a run, print `thread_id` + `agent_run_id`.
2. **`status.py`** -- Check run status, or poll with `--wait`.
3. **`sandbox.py`** -- Sandbox file operations: `ls`, `cat`, `download`, `upload`, `rm`.

## Workflow

```bash
# 1. Start a task
python3 start.py -p "user question"
# → {thread_id, agent_run_id}

# 2. Wait for completion
python3 status.py <agent_run_id> --wait

# 3. Download results
python3 sandbox.py download <thread_id> -o ~/cc_tmp/sciencepal/<run_id>/

# Sandbox operations
python3 sandbox.py ls <sandbox_id> /workspace
python3 sandbox.py cat <sandbox_id> /workspace/report.md
python3 sandbox.py upload <sandbox_id> local.pdb /workspace/input.pdb
python3 sandbox.py rm <sandbox_id> /workspace/tmp.txt
```

## Rules

- Print `thread_id` and `agent_run_id` immediately after starting.
- Terminal statuses: `completed`, `failed`, `stopped`. Only download for `completed`.
- Output files go to `~/cc_tmp/sciencepal/<run_id>/`, not inside any project repo.
- `/agent/initiate` uses **form-data**, not JSON.
