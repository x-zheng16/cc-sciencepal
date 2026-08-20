# cc-sciencepal

A Claude Code plugin for [SciencePal](https://sciencepal.ai), a science research agent platform with sandboxed compute environments.

## What it does

Run and manage SciencePal research agents (biology, materials, protein, plasma, patents) without leaving Claude Code. The plugin ships a single skill, `sciencepal`, backed by six small Python scripts:

- Start a research task and get back its `thread_id` and `agent_run_id`.
- Continue an existing session: answer the agent's clarifying questions, or steer a run that already finished.
- List every session on the account, check the status of one run, or stop a run.
- Browse, read, upload, delete, and bulk-download the files in a run's sandbox.

Two environments are supported side by side, staging (`stg`) and production (`prd`), selected per invocation with `--env`. Sessions run concurrently, each with its own project and sandbox, so several can be in flight at once.

## Requirements

- Python 3.12 or newer.
- [uv](https://docs.astral.sh/uv/), used to run the scripts with their one dependency (`httpx`) resolved on the fly.
- A SciencePal account, and an access token for each environment you intend to use.

## Install

### Claude Code plugin (recommended)

```bash
/plugin install x-zheng16/cc-sciencepal
```

### npx skills

```bash
npx skills add x-zheng16/cc-sciencepal
```

## Setup

Credentials are read from the environment. Export them from `~/.zshenv.local` (or any shell startup file that is not checked into version control) so they are inherited by every session:

```bash
# staging
export SCIENCEPAL_STG_ACCESS_TOKEN="<your stg token>"
export SCIENCEPAL_STG_BASE_URL="https://stg.sciencepal.ai/api"
export SCIENCEPAL_STG_SUPABASE_ANON_KEY="<stg anon key>"

# production
export SCIENCEPAL_PRD_ACCESS_TOKEN="<your prd token>"
export SCIENCEPAL_PRD_BASE_URL="https://sciencepal.ai/api"
export SCIENCEPAL_PRD_SUPABASE_ANON_KEY="<prd anon key>"
```

| Variable | Required | Notes |
| --- | --- | --- |
| `SCIENCEPAL_STG_ACCESS_TOKEN` | Yes, for `--env stg` | Your personal access token for staging. |
| `SCIENCEPAL_PRD_ACCESS_TOKEN` | Yes, for `--env prd` | Your personal access token for production. |
| `SCIENCEPAL_STG_BASE_URL` | No | Defaults to `https://stg.sciencepal.ai/api`. |
| `SCIENCEPAL_PRD_BASE_URL` | No | Defaults to `https://sciencepal.ai/api`. |
| `SCIENCEPAL_STG_SUPABASE_ANON_KEY` | Only for `followup.py` | The public client key the web app ships. |
| `SCIENCEPAL_PRD_SUPABASE_ANON_KEY` | Only for `followup.py` | Same, for production. |
| `SCIENCEPAL_ACCESS_TOKEN` | No (legacy) | Accepted as a production-only fallback when `SCIENCEPAL_PRD_ACCESS_TOKEN` is unset. Prefer the explicit per-environment names. |

`followup.py` needs the Supabase anon key because it writes the follow-up message through the same two-step path the web frontend uses: a PostgREST message insert, then an agent start. The other five scripts talk only to the SciencePal API and need just the access token. The Supabase project URLs are built in; `SCIENCEPAL_STG_SUPABASE_URL` and `SCIENCEPAL_PRD_SUPABASE_URL` override them if you ever need to point elsewhere.

As an alternative to shell exports, the scripts also merge `~/.claude/.env` (same `KEY=value` names) into the environment at startup. Values already present in the real environment win, so exports take precedence over that file.

Access tokens are short-lived JWTs and are refreshed manually. When one expires, the scripts exit with an explicit hint rather than a raw HTTP error: log into the web app, copy a fresh token, and update the variable. Never print or log a token value.

## Usage

Every script lives in `skills/sciencepal/scripts/` and is run the same way, from that directory:

```bash
uv run --no-project --with httpx python3 <script>.py --env stg
```

`--env` (short form `-e`) accepts `stg` or `prd` and **defaults to `stg`**, so pass `--env prd` explicitly whenever you mean production. The examples below abbreviate the runner as `python3 <script>.py` for readability; use the full `uv run` form shown above.

### Start a run

```bash
python3 start.py -p "survey recent solid-state electrolyte chemistries for Li metal anodes"
python3 start.py --env prd -p "..." --no-web-search
python3 start.py -p "..." --select manual --agent-id <agent_id>
```

Prints the JSON response, which carries the `thread_id` and the `agent_run_id`. Keep both: status checks and stops take the run ID, follow-ups and downloads take the thread ID. Web search is on unless you pass `--no-web-search`, and agent selection is automatic unless you pass `--select manual` with `--agent-id`.

By default a fresh task does not run straight through to completion. The agent asks one round of clarifying questions and parks awaiting your answer. Reply with `followup.py`, or pre-empt the gate by writing a fully specified prompt that states every parameter and explicitly instructs the agent not to ask.

### Continue an existing session

```bash
python3 followup.py -t <thread_id> -p "yes, proceed with the 2020-2024 window"
python3 followup.py -t <thread_id> -p "..." --no-start
```

This is the way to answer clarifying questions, steer a running session, or restart a finished one with new instructions. `--no-start` inserts the message without starting an agent run, queueing it for the next one.

### List sessions

```bash
python3 sessions.py
python3 sessions.py --env prd --json
python3 sessions.py --since 2026-08-01T00:00:00Z
```

Lists the account's projects with their run statuses. `--json` prints the raw response; `--since` takes an ISO 8601 timestamp and limits the list to sessions updated after it.

### Check status

```bash
python3 status.py <agent_run_id>
python3 status.py <agent_run_id> --wait
python3 status.py <agent_run_id> --wait --interval 30 --timeout 7200
```

One-shot by default. With `--wait` it polls until the run reaches a terminal status (`completed`, `failed`, or `stopped`), printing each transition. The poll interval defaults to 10 seconds and the overall wait to 3600 seconds; do not poll faster than every 10 seconds. The exit status is non-zero if the run ends as `failed` or `stopped`, or if the timeout is reached.

### Stop a run

```bash
python3 stop.py <agent_run_id> --env prd
```

### Sandbox files

`sandbox.py` takes `--env` before the subcommand, since the flag belongs to the top-level parser:

```bash
python3 sandbox.py --env prd download <thread_id> -o ./sciencepal-out/
python3 sandbox.py ls <sandbox_id> /workspace
python3 sandbox.py cat <sandbox_id> /workspace/report.md
python3 sandbox.py upload <sandbox_id> ./local.pdb /workspace/input.pdb
python3 sandbox.py rm <sandbox_id> /workspace/tmp.txt
```

`download` is the odd one out: it takes a `thread_id` and resolves the sandbox itself, then walks the sandbox recursively and mirrors every file locally. It reads `/workspace` unless you point `--root` elsewhere, and writes to `./downloads/<thread_id>` unless you pass `-o`. All other subcommands take a `sandbox_id` directly. `ls` defaults to `/`.

Task results are written to `/workspace` inside the sandbox, typically a `report.md` plus `data/` and `figures/` directories. Anything under `/app` is read-only base image content, not task output. Write downloads to a scratch directory outside any repository you care about.

A sandbox stops automatically after roughly 10 minutes of idle time, so a run you return to much later may need to be reactivated before its files are reachable. Avoid downloading from a `failed` or `stopped` run: its sandbox state may be incomplete.

## Loop and compact directives

SciencePal understands two directives sent as ordinary prompt text. Both are dispatched only on the insert-then-start path, so arm them with `followup.py` against an existing thread; `start.py` alone will not.

`/loop <interval> <prompt>` re-runs the prompt on a fixed interval (60 seconds minimum, 100 ticks maximum) until the agent calls its `stop_loop` tool or a human turn clears the loop. Each tick runs unattended, so the prompt must be a self-contained directive that never asks a question, and it must state its own completion condition. `/loop stop` clears an armed loop deterministically, including ticks already queued. The self-paced form, `/loop <prompt>` with no interval, is refused at dispatch and arms nothing: always pass an interval.

```bash
python3 followup.py -t <thread_id> -p "/loop 30m Keep working autonomously and never ask questions: each pass, search for new literature, update the review and its tables, and fill the gaps left by the previous pass. Call stop_loop once coverage is complete, citations are in place, and the draft is internally consistent."
```

`/compact [focus hint]` compresses a long session into a resumption summary. It starts no agent run and does not clear an armed loop. Each summary is also archived to the thread's sandbox under `/workspace/compact/`, and the response reports the path, so it can be read back with the ordinary sandbox file commands.

The skill documentation in `skills/sciencepal/SKILL.md` carries the full guidance, including loop prompt patterns, per-domain prompt engineering advice, result quality signals, and the API reference.

## License

MIT
