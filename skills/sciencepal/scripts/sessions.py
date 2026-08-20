#!/usr/bin/env python3
"""List SciencePal sessions for the account, with an identifier you can act on.

`manage all sessions` starts here: see what is running or done across the account,
then act on a specific one with followup.py / status.py / stop.py / sandbox.py.

WHY TWO ENDPOINTS. /projects/statuses returns only {project_id, status}, and no
command in this plugin accepts a project_id: follow-ups and downloads take a
thread_id, status checks and stops take an agent_run_id. So that listing could tell
you a session existed and give you no way to reach it, which bit for real when three
runs created by timed-out starts were visible and unreachable.

/dashboard/personal-conversations returns projects, threads and statuses together, so
joining them on project_id yields a name, a thread_id and a status per row. Confirmed
against the DEPLOYED schema rather than a checkout: it is in the live OpenAPI document
on both environments, and the response carries thread_id on every thread row. Note the
spec lives at the HOST root, not under the /api base, so fetching it needs the ../ hop.

It takes no parameters, so --since is filtered client-side on last_message_at. Pass
--statuses-only to use the older, narrower endpoint, which does accept a server-side
since and is the fallback if the dashboard route ever goes away.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from _spclient import make_client, add_env_arg


def render_status(row: dict) -> str:
    """Three distinct states, kept distinct.

    The key is usually present with a string. It is sometimes present with a JSON
    null, which a dict default does not cover and which used to print as "None";
    per the service owner that means the project has no agent-run row to report. And
    it could be absent entirely, which is a malformed row rather than a project
    without runs, so it must not be disguised as null.
    """
    if "status" not in row:
        return "?"
    return row["status"] if row["status"] is not None else "-"


async def main() -> None:
    p = argparse.ArgumentParser(description="List SciencePal sessions")
    add_env_arg(p)
    p.add_argument("--since", default=None, help="ISO8601; only sessions active after this time")
    p.add_argument("--json", action="store_true", help="print the raw response")
    p.add_argument(
        "--statuses-only",
        action="store_true",
        help="use /projects/statuses (no thread_id, but server-side --since)",
    )
    args = p.parse_args()

    async with make_client(args.env) as c:
        if args.statuses_only:
            params = {"since": args.since} if args.since else None
            r = await c.get("/projects/statuses", params=params)
        else:
            r = await c.get("/dashboard/personal-conversations")
        r.raise_for_status()
        data = r.json()

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if args.statuses_only:
        rows = data.get("statuses", []) if isinstance(data, dict) else (data or [])
        print(f"[{args.env}] {len(rows)} session(s):")
        for s in rows:
            print(f"  {s.get('project_id', '?')}  {render_status(s)}")
        return

    projects = {p["project_id"]: p for p in data.get("projects", []) if p.get("project_id")}
    status_by_project = {
        s["project_id"]: render_status(s)
        for s in data.get("statuses", [])
        if s.get("project_id")
    }

    # Newest thread per project. A project can carry several; the one a follow-up
    # should target is the most recently active, and last_message_at is the field
    # the server sorts conversations by.
    newest: dict[str, dict] = {}
    for t in data.get("threads", []):
        pid = t.get("project_id")
        if not pid:
            continue
        stamp = t.get("last_message_at") or t.get("updated_at") or ""
        prev = newest.get(pid)
        if prev is None or stamp >= (prev.get("last_message_at") or prev.get("updated_at") or ""):
            newest[pid] = t

    rows = []
    for pid, status in status_by_project.items():
        t = newest.get(pid)
        stamp = (t or {}).get("last_message_at") or (t or {}).get("updated_at") or ""
        if args.since and stamp and stamp < args.since:
            continue
        rows.append((stamp, pid, (t or {}).get("thread_id"), status,
                     (projects.get(pid) or {}).get("name") or ""))
    rows.sort(reverse=True)

    print(f"[{args.env}] {len(rows)} session(s), newest first:")
    if args.since:
        print(f"  (filtered client-side to last activity >= {args.since})")
    for stamp, pid, tid, status, name in rows:
        print(f"  {status:<13} thread {tid or '(none)':<36}  {name[:48]}")
        print(f"  {'':<13} project {pid}")


if __name__ == "__main__":
    asyncio.run(main())
