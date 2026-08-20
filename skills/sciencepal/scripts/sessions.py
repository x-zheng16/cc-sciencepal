#!/usr/bin/env python3
"""List SciencePal sessions (projects + their run statuses) for the account.

`manage all sessions` starts here: see what's running / done across the account,
then act with status.py / stop.py / sandbox.py on a specific run.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from _spclient import make_client, add_env_arg


async def main() -> None:
    p = argparse.ArgumentParser(description="List SciencePal sessions (projects + statuses)")
    add_env_arg(p)
    p.add_argument("--since", default=None, help="ISO8601; only sessions updated after this time")
    p.add_argument("--json", action="store_true", help="print raw JSON")
    args = p.parse_args()

    async with make_client(args.env) as c:
        params = {"since": args.since} if args.since else None
        r = await c.get("/projects/statuses", params=params)
        r.raise_for_status()
        data = r.json()

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    rows = data.get("statuses", []) if isinstance(data, dict) else (data or [])
    print(f"[{args.env}] {len(rows)} session(s):")
    for s in rows:
        # `status` is sometimes present with a JSON null rather than absent, so the
        # dict default alone does not cover it and the row would print "None".
        status = s.get("status") or "-"
        print(f"  {s.get('project_id', '?')}  {status}")


if __name__ == "__main__":
    asyncio.run(main())
