#!/usr/bin/env python3
"""Send a follow-up message to an EXISTING SciencePal session and re-start its agent.

Two-step wire protocol (mirrors the web frontend):
1. Insert the user message row via Supabase PostgREST (anon apikey + the user's
   own JWT; RLS restricts the insert to threads the user owns), and read the
   inserted row back to confirm it landed on the thread that was asked for.
2. POST /thread/{thread_id}/agent/start to run the agent on the updated thread.

The two steps are correlated only by ORDER. The start endpoint takes no message
id and resolves its target by taking the newest human user row on the thread,
so the insert must land first and a second insert racing between the two steps
would be picked instead.

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


def _parse_inserted_message_id(response: httpx.Response, thread_id: str) -> str:
    """Return the database-generated message_id from one PostgREST insert.

    This is a DIAGNOSTIC check, not a correlation mechanism. The start endpoint
    accepts no message id and resolves its target by taking the newest human
    user row on the thread, so this id is never sent anywhere. What it buys is
    that a 2xx from PostgREST stops being taken on faith: an insert that landed
    on the wrong thread, landed as the wrong row type, or did not land at all
    is caught here instead of at the next step, where it would look like the
    agent quietly ignoring the follow-up.
    """
    try:
        rows = response.json()
    except ValueError as error:
        raise SystemExit(
            "Message insert failed: PostgREST returned a non-JSON representation"
        ) from error

    if not isinstance(rows, list) or len(rows) != 1:
        raise SystemExit(
            "Message insert failed: PostgREST did not return exactly one inserted row"
        )
    row = rows[0]
    if not isinstance(row, dict):
        raise SystemExit("Message insert failed: PostgREST returned a malformed row")
    if row.get("thread_id") != thread_id or row.get("type") != "user":
        raise SystemExit(
            f"Message insert failed: the inserted row does not match what was asked for "
            f"(thread_id={row.get('thread_id')!r}, type={row.get('type')!r})"
        )

    message_id = row.get("message_id")
    if not isinstance(message_id, str) or not message_id.strip():
        raise SystemExit("Message insert failed: the inserted row carries no message_id")
    return message_id


async def insert_user_message(env: str, thread_id: str, text: str) -> str:
    """PostgREST insert matching the frontend's row shape exactly:
    type='user', is_llm_message=true, content = JSON-STRING envelope.

    Returns the inserted row's message_id, so the caller can quote it when a
    later step fails and the row must be inspected or removed by hand.
    """
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
            params={"select": "message_id,thread_id,type"},
            headers={
                "apikey": anon,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            content=json.dumps(row, ensure_ascii=False),
        )
        if r.status_code == 401:
            raise SystemExit(
                f"SciencePal {env} token expired/invalid (401) at Supabase. "
                f"Refresh SCIENCEPAL_{env.upper()}_ACCESS_TOKEN (see SKILL.md)."
            )
        if not r.is_success:
            raise SystemExit(
                f"Message insert failed: HTTP {r.status_code} {r.text[:300]} "
                f"(RLS denies inserts into threads you don't own; check thread_id/env)"
            )
        return _parse_inserted_message_id(r, thread_id)


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

    message_id = await insert_user_message(args.env, args.thread, args.prompt)
    if args.no_start:
        print(
            json.dumps(
                {
                    "thread_id": args.thread,
                    "message_id": message_id,
                    "message": "inserted",
                    "started": False,
                }
            )
        )
        return

    async with make_client(args.env) as c:
        r = await c.post(f"/thread/{args.thread}/agent/start", json={})
        r.raise_for_status()
        out = r.json()
        out["thread_id"] = args.thread
        out["message_id"] = message_id
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
