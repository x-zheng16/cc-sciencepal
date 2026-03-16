---
name: sciencepal
description: |
  Run SciencePal science research agents and manage sandbox environments.
  Use when user mentions SciencePal, or wants to:
  (1) run a science research task (biology, material, protein, plasma, patent analysis),
  (2) check agent run status or wait for completion,
  (3) browse, download, upload, or delete files in a SciencePal sandbox.
  Keywords: sciencepal, research agent, sandbox, biology agent, material agent, protein structure, plasma simulation.
  Do NOT use for general web search, paper search, or non-SciencePal tasks.
---

# SciencePal

Science research agent platform with sandbox compute environments.

## Decision Tree

```
User request
├── "run/start/analyze with SciencePal" → start.py
├── "check status / is it done"         → status.py (one-shot or --wait)
├── "download results"                  → sandbox.py download <thread_id>
├── "show/list/browse sandbox files"    → sandbox.py ls <sandbox_id> <path>
├── "read a sandbox file"              → sandbox.py cat <sandbox_id> <path>
├── "upload file to sandbox"           → sandbox.py upload <sandbox_id> <local> <remote>
└── "delete sandbox file"              → sandbox.py rm <sandbox_id> <path>
```

## Scripts

All scripts: `uv run --project ~/.claude/cc-python python3 <script>`.
Working directory: this skill's `scripts/` folder.

### start.py -- Start a run

```bash
python3 start.py -p "user question"
# → {thread_id, agent_run_id}
```

Print both IDs immediately. User needs them for status checks and downloads.

### status.py -- Check or wait for status

```bash
python3 status.py <agent_run_id>          # one-shot check
python3 status.py <agent_run_id> --wait   # poll until terminal
```

Terminal statuses: `completed`, `failed`, `stopped`.

### sandbox.py -- Sandbox file operations

```bash
python3 sandbox.py ls <sandbox_id> /workspace
python3 sandbox.py cat <sandbox_id> /workspace/report.md
python3 sandbox.py download <thread_id> -o ~/cc_tmp/sciencepal/<run_id>/
python3 sandbox.py upload <sandbox_id> local.pdb /workspace/input.pdb
python3 sandbox.py rm <sandbox_id> /workspace/tmp.txt
```

`download` takes thread_id (resolves sandbox automatically). All other subcommands take sandbox_id directly.

## API Reference

**LOAD [`references/api.md`](references/api.md) when you need endpoint details, request/response formats, or query parameters.**

Do NOT load for routine script usage -- the scripts handle API calls internally.

## NEVER

- NEVER send JSON body to `/agent/initiate` -- it requires **form-data**. JSON returns 422.
- NEVER assume sandbox is alive -- it auto-stops after 10min idle. Call `ensure-active` first if the run finished a while ago.
- NEVER download from a `failed` or `stopped` run -- sandbox may have incomplete/corrupt state.
- NEVER put downloaded files inside a project repo -- always use `~/cc_tmp/sciencepal/<run_id>/`.
- NEVER poll status faster than every 10 seconds -- respect rate limits.

## Error Handling

| Error                        | Cause                                 | Fix                                     |
| ---------------------------- | ------------------------------------- | --------------------------------------- |
| 401 Unauthorized             | Token expired or invalid              | Refresh token at sciencepal.ai          |
| 404 on `/agent-run/{id}`     | Invalid run ID                        | Check ID from start.py output           |
| 404 on sandbox file read     | File doesn't exist or sandbox destroyed | Try `sandbox.py ls` first to verify   |
| 422 on `/agent/initiate`     | Sent JSON instead of form-data        | Scripts handle this correctly           |
| 500 on sandbox operations    | Sandbox crashed or being archived     | Call `ensure-active`, retry             |
| Timeout on `--wait`          | Task taking too long                  | Check status manually, increase timeout |

## Rules

- Print `thread_id` and `agent_run_id` immediately after starting.
- Output files go to `~/cc_tmp/sciencepal/<run_id>/`, not inside any project repo.
- Agent task results are in `/workspace` inside the sandbox.
- Tool/model files live in `/app` -- these are read-only base image contents, not task outputs.
