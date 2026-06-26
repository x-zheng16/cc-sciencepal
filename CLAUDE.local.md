# cc-sciencepal

Claude Code plugin for SciencePal -- science research agent platform.

## Skills

- `sciencepal` -- Start research agent runs (material, bio, protein, plasma, patent), list/status/stop sessions, download results -- across **stg + prd** (`--env`). Sessions run concurrently.

## Environment

Requires in `~/.zshenv.local` (gitignored) -- two credential sets:
- `SCIENCEPAL_STG_ACCESS_TOKEN` + `SCIENCEPAL_STG_BASE_URL` (`https://stg.sciencepal.ai/api`)
- `SCIENCEPAL_PRD_ACCESS_TOKEN` + `SCIENCEPAL_PRD_BASE_URL` (`https://sciencepal.ai/api`)

Tokens are short-lived Supabase JWTs (manual-refresh): on a 401 the script prints a refresh hint -- log into the web app, copy a fresh token, update the var. (Legacy `SCIENCEPAL_ACCESS_TOKEN` still works as a prd fallback.)

## Running scripts

```bash
# from skills/sciencepal/scripts/ ; every script takes --env stg|prd (default stg)
uv run --no-project --with httpx python3 <script>.py --env stg
```
