# cc-sciencepal

Claude Code plugin for SciencePal -- science research agent platform.

## Skills

- `sciencepal` -- Start research agent runs (material, bio, protein, plasma, patent), poll status, download results.

## Environment

Requires in `~/.claude/.env`:
- `SCIENCEPAL_ACCESS_TOKEN`
- `SCIENCEPAL_BASE_URL` (optional, defaults to `https://sciencepal.ai/api`)

## Running scripts

```bash
uv run --project ~/.claude/cc-python python3 scripts/<script>.py
```
