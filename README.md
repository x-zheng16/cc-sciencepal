# cc-sciencepal

Claude Code plugin for [SciencePal](https://sciencepal.ai) -- science research agent platform.

## What it does

Run SciencePal research agents (biology, material, protein, plasma, patent) from Claude Code.
Start tasks, check status, and manage sandbox files (list, read, download, upload, delete).

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

## Usage

```bash
# Start a task
python3 start.py -p "analyze protein structure of PDB 1ABC"

# Check status (one-shot or wait)
python3 status.py <agent_run_id>
python3 status.py <agent_run_id> --wait

# Download results
python3 sandbox.py download <thread_id> -o ~/cc_tmp/sciencepal/out/

# Browse sandbox files
python3 sandbox.py ls <sandbox_id> /workspace
python3 sandbox.py cat <sandbox_id> /workspace/report.md

# Upload / delete files
python3 sandbox.py upload <sandbox_id> local.pdb /workspace/input.pdb
python3 sandbox.py rm <sandbox_id> /workspace/tmp.txt
```

## License

MIT
