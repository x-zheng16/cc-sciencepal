#!/usr/bin/env python3
"""Send a follow-up message to an EXISTING SciencePal session and re-start its agent.

Two-step wire protocol (mirrors the web frontend):
1. Insert the user message row via Supabase PostgREST (anon apikey + the user's
   own JWT; RLS restricts the insert to threads the user owns).
2. POST /thread/{thread_id}/agent/start to run the agent on the updated thread.

Use this to answer an agent's clarifying questions (the brainstorming gate),
steer a running session, or continue a finished one.

Supabase anon keys are env-only (public repo — no embedded vendor credentials):
SCIENCEPAL_STG_SUPABASE_ANON_KEY / SCIENCEPAL_PRD_SUPABASE_ANON_KEY in
~/.zshenv.local or ~/.claude/.env.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os

import httpx

from _spclient import make_client, add_env_arg, resolve, _load_dotenv

SUPABASE_URLS = {
    "stg": "https://iupafdgylwzxfiycgnki.supabase.co",
    "prd": "https://dwkmdejtbxsavupvhjmc.supabase.co",
}


def resolve_supabase(env: str) -> tuple[str, str]:
    """Return (supabase_url, anon_key) for env. URLs are public (shipped in the
    frontend bundle); anon keys come from the environment only."""
    _load_dotenv()
    url = os.getenv(f"SCIENCEPAL_{env.upper()}_SUPABASE_URL") or SUPABASE_URLS[env]
    anon = os.getenv(f"SCIENCEPAL_{env.upper()}_SUPABASE_ANON_KEY")
    if not anon:
        raise SystemExit(
            f"Missing SCIENCEPAL_{env.upper()}_SUPABASE_ANON_KEY. Add it to "
            f"~/.zshenv.local (the anon key is the public client key the web app "
            f"ships; copy it from the frontend bundle or ask the backend owner)."
        )
    return url, anon


async def insert_user_message(env: str, thread_id: str, text: str) -> None:
    """PostgREST insert matching the frontend's row shape exactly:
    type='user', is_llm_message=true, content = JSON-STRING envelope."""
    token, _ = resolve(env)
    sb_url, anon = resolve_supabase(env)
    row = {
        "thread_id": thread_id,
        "type": "user",
        "is_llm_message": True,
        "content": json.dumps({"role": "user", "content": text}, ensure_ascii=False),
        "metadata": {},
    }
    async with httpx.AsyncClient(timeout=30.0, trust_env=False) as c:
        r = await c.post(
            f"{sb_url}/rest/v1/messages",
            headers={
                "apikey": anon,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            content=json.dumps(row, ensure_ascii=False),
        )
        if r.status_code == 401:
            raise SystemExit(
                f"SciencePal {env} token expired/invalid (401) at Supabase. "
                f"Refresh SCIENCEPAL_{env.upper()}_ACCESS_TOKEN (see SKILL.md)."
            )
        if r.status_code not in (200, 201, 204):
            raise SystemExit(
                f"Message insert failed: HTTP {r.status_code} {r.text[:300]} "
                f"(RLS denies inserts into threads you don't own — check thread_id/env)"
            )


async def main() -> None:
    p = argparse.ArgumentParser(
        description="Send a follow-up message to an existing SciencePal session"
    )
    add_env_arg(p)
    p.add_argument("--thread", "-t", required=True, help="Existing thread_id")
    p.add_argument("--prompt", "-p", required=True, help="Follow-up message text")
    p.add_argument(
        "--no-start",
        action="store_true",
        help="Only insert the message; don't start an agent run (queue it for the next run)",
    )
    args = p.parse_args()

    await insert_user_message(args.env, args.thread, args.prompt)
    if args.no_start:
        print(json.dumps({"thread_id": args.thread, "message": "inserted", "started": False}))
        return

    async with make_client(args.env) as c:
        r = await c.post(f"/thread/{args.thread}/agent/start", json={})
        r.raise_for_status()
        out = r.json()
        out["thread_id"] = args.thread
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
