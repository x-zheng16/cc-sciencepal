---
name: sciencepal
version: 0.1.1
quality:
  grade: C
  score: 84
  date: 2026-04-07
description: >-
  Run SciencePal science research agents and manage sandbox environments.
  Use when user mentions SciencePal, or wants to start a science research task (biology, material, protein, plasma, patent analysis),
  check agent run status, or browse, download, upload, and delete files in a SciencePal sandbox.
  Do NOT use for general web search, paper search, or non-SciencePal tasks.
---

# SciencePal

Science research agent platform with sandbox compute environments.

## Decision Tree

```
User request
+-- "run/start/analyze with SciencePal" --> start.py
+-- "check status / is it done"         --> status.py (one-shot or --wait)
+-- "download results"                  --> sandbox.py download <thread_id>
+-- "show/list/browse sandbox files"    --> sandbox.py ls <sandbox_id> <path>
+-- "read a sandbox file"              --> sandbox.py cat <sandbox_id> <path>
+-- "upload file to sandbox"           --> sandbox.py upload <sandbox_id> <local> <remote>
+-- "delete sandbox file"              --> sandbox.py rm <sandbox_id> <path>
```

## Scripts

All scripts: `uv run --project ~/.claude/cc-python python3 <script>`.
Working directory: this skill's `scripts/` folder.

### start.py -- Start a run

```bash
python3 start.py -p "user question"
# -> {thread_id, agent_run_id}
```

Print both IDs immediately.
User needs them for status checks and downloads.

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

`download` takes thread_id (resolves sandbox automatically).
All other subcommands take sandbox_id directly.

## Agent Orchestration Patterns

### Task Decomposition

SciencePal agents handle multi-step scientific workflows internally.
The user provides a high-level research question; the agent decomposes it into sub-tasks (literature search, data retrieval, analysis, synthesis).
Do not attempt to manually orchestrate sub-steps -- let the agent handle decomposition.

### Long-Running Tasks

Science tasks often take 5-30 minutes.
After starting a run, use `status.py --wait` to poll automatically rather than checking manually in a loop.
If the user needs to do other work, report the run IDs and offer to check later.

### Result Interpretation

Downloaded results land in `/workspace` inside the sandbox.
Common output patterns:
- `report.md` or `summary.md` -- main findings.
- `data/` -- raw or processed data files.
- `figures/` -- generated plots or visualizations.

Read the report file first to understand what the agent produced, then examine data files as needed.

### Error Recovery

If a run fails:
1. Check the status output for error messages.
2. Review sandbox files for partial results (`sandbox.py ls`).
3. Reformulate the prompt with more specific constraints and restart.

Sandbox auto-stops after 10 minutes of idle time.
If returning to a completed run after a delay, call `ensure-active` before accessing files.

## API Reference

**LOAD [`references/api.md`](references/api.md) when you need endpoint details, request/response formats, or query parameters.**

Do NOT load for routine script usage -- the scripts handle API calls internally.

## NEVER

- NEVER send JSON body to `/agent/initiate` -- it requires **form-data**. JSON returns 422.
- NEVER assume sandbox is alive -- it auto-stops after 10min idle. Call `ensure-active` first if the run finished a while ago.
- NEVER download from a `failed` or `stopped` run -- sandbox may have incomplete/corrupt state.
- NEVER put downloaded files inside a project repo -- always use `~/cc_tmp/sciencepal/<run_id>/`.
- NEVER poll status faster than every 10 seconds -- respect rate limits.
- NEVER expose or log the `SCIENCEPAL_ACCESS_TOKEN` value.

## Error Handling

| Error                     | Cause                                   | Fix                                     |
| ------------------------- | --------------------------------------- | --------------------------------------- |
| 401 Unauthorized          | Token expired or invalid                | Refresh token at sciencepal.ai          |
| 404 on `/agent-run/{id}`  | Invalid run ID                          | Check ID from start.py output           |
| 404 on sandbox file read  | File doesn't exist or sandbox destroyed | Try `sandbox.py ls` first to verify     |
| 422 on `/agent/initiate`  | Sent JSON instead of form-data          | Scripts handle this correctly           |
| 500 on sandbox operations | Sandbox crashed or being archived       | Call `ensure-active`, retry             |
| Timeout on `--wait`       | Task taking too long                    | Check status manually, increase timeout |

## Rules

- Print `thread_id` and `agent_run_id` immediately after starting.
- Output files go to `~/cc_tmp/sciencepal/<run_id>/`, not inside any project repo.
- Agent task results are in `/workspace` inside the sandbox.
- Tool/model files live in `/app` -- these are read-only base image contents, not task outputs.
