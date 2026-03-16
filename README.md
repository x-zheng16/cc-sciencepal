# cc-sciencepal

Claude Code plugin for [SciencePal](https://sciencepal.ai) -- science research agent platform.

## What it does

Run SciencePal research agents (biology, material, protein, plasma, patent) from Claude Code.
Start tasks, poll status, and download results from sandbox environments.

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

Add to `~/.claude/.env`:

```bash
SCIENCEPAL_BASE_URL=https://sciencepal.ai/api
SCIENCEPAL_ACCESS_TOKEN=<your-token>
```

Get your token from [SciencePal](https://sciencepal.ai).

## API endpoints (reverse-engineered)

| Endpoint                                            | Method | Purpose             |
| --------------------------------------------------- | ------ | ------------------- |
| `/agent/initiate`                                   | POST   | Start a new run     |
| `/agent-run/{id}`                                   | GET    | Check run status    |
| `/agent-run/{id}/stop`                              | POST   | Stop a run          |
| `/thread/{id}/sandbox`                              | GET    | Get sandbox info    |
| `/sandboxes/{id}/files?path=`                       | GET    | List files          |
| `/sandboxes/{id}/files/content?path=`               | GET    | Read file content   |
| `/sandboxes/{id}/files`                             | POST   | Upload file         |
| `/sandboxes/{id}/files`                             | DELETE | Delete file         |
| `/project/{id}/sandbox/ensure-active`               | POST   | Wake up sandbox     |

## Scripts

Run from `skills/sciencepal/scripts/`:

```bash
# Start a task
uv run --project ~/.claude/cc-python python3 start_run.py --prompt "your question"

# Poll and download results
uv run --project ~/.claude/cc-python python3 poll_and_download.py \
  --agent-run-id <id> --thread-id <id> --output-dir ~/cc_tmp/sciencepal/<id>/
```

## License

MIT
