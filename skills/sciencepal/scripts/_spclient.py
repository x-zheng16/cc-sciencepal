#!/usr/bin/env python3
"""Shared env-aware SciencePal HTTP client (stg | prd).

Holds two credential sets so both environments can be driven from one client:
- stg: SCIENCEPAL_STG_ACCESS_TOKEN + SCIENCEPAL_STG_BASE_URL (https://stg.sciencepal.ai/api)
- prd: SCIENCEPAL_PRD_ACCESS_TOKEN + SCIENCEPAL_PRD_BASE_URL (https://sciencepal.ai/api)

Keys live in ~/.zshenv.local (gitignored, inherited at shell launch) or ~/.claude/.env.
SciencePal access tokens are short-lived Supabase JWTs; if a call 401s, the token
expired -> refresh it (see SKILL.md). NEVER print a token value.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

DEFAULTS = {
    "stg": "https://stg.sciencepal.ai/api",
    "prd": "https://sciencepal.ai/api",
}


def _load_dotenv() -> None:
    """Merge ~/.claude/.env into os.environ (does not override the live env,
    which already carries ~/.zshenv.local exports)."""
    env_path = Path.home() / ".claude" / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("\"'")
        if k and k not in os.environ:
            os.environ[k] = v


def resolve(env: str) -> tuple[str, str]:
    """Return (token, base_url) for env in {stg, prd}. Raises if the token is absent."""
    env = (env or "stg").lower()
    if env not in DEFAULTS:
        raise SystemExit(f"--env must be 'stg' or 'prd', got {env!r}")
    _load_dotenv()
    token = os.getenv(f"SCIENCEPAL_{env.upper()}_ACCESS_TOKEN")
    if not token and env == "prd":
        token = os.getenv("SCIENCEPAL_ACCESS_TOKEN")  # legacy single-token fallback
    if not token:
        raise SystemExit(
            f"Missing SCIENCEPAL_{env.upper()}_ACCESS_TOKEN. Add it to ~/.zshenv.local "
            f"(gitignored). SciencePal tokens are short-lived; refresh at the web app."
        )
    base_url = os.getenv(f"SCIENCEPAL_{env.upper()}_BASE_URL") or DEFAULTS[env]
    return token, base_url


def make_client(env: str, timeout: float = 60.0) -> httpx.AsyncClient:
    """Build an authed AsyncClient for the chosen env, forced DIRECT: the proxy
    variables are cleared and trust_env=False, so a proxy configured in the
    environment is never used for these calls.

    Tokens are short-lived (manual-refresh model): on 401 the client exits with a clear
    'refresh your token' hint rather than a raw httpx error.

    `timeout` is per-request and defaults to 60s, which suits every read endpoint.
    /agent/initiate provisions a sandbox before it answers and routinely exceeds that,
    so start.py raises it; see the note there about why a timeout is not a failure.
    """
    token, base_url = resolve(env)
    web = base_url.rsplit("/api", 1)[0]

    async def _on_response(r: httpx.Response) -> None:
        if r.status_code == 401:
            raise SystemExit(
                f"SciencePal {env} token expired/invalid (401). Refresh it: log in at {web}, "
                f"copy a fresh access token, and update SCIENCEPAL_{env.upper()}_ACCESS_TOKEN "
                f"in ~/.zshenv.local."
            )

    for k in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=timeout,
        trust_env=False,
        event_hooks={"response": [_on_response]},
    )


def add_env_arg(parser) -> None:
    """Standard --env stg|prd (default stg) for every script."""
    parser.add_argument("--env", "-e", default="stg", choices=["stg", "prd"],
                        help="SciencePal environment (default: stg)")
