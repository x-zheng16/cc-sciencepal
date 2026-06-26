#!/usr/bin/env python3
"""Check or wait for agent run status."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

from _spclient import make_client, add_env_arg

TERMINAL = {"completed", "failed", "stopped"}


async def main() -> None:
    p = argparse.ArgumentParser(description="Check or wait for agent run status")
    add_env_arg(p)
    p.add_argument("agent_run_id", help="Agent run ID")
    p.add_argument("--wait", "-w", action="store_true", help="Poll until complete")
    p.add_argument("--interval", "-i", type=float, default=10, help="Poll interval (seconds)")
    p.add_argument("--timeout", type=float, default=3600, help="Max wait time (seconds)")
    args = p.parse_args()

    async with make_client(args.env) as c:
        if not args.wait:
            r = await c.get(f"/agent-run/{args.agent_run_id}")
            r.raise_for_status()
            print(json.dumps(r.json(), ensure_ascii=False, indent=2))
            return

        start = asyncio.get_event_loop().time()
        last = None
        while True:
            r = await c.get(f"/agent-run/{args.agent_run_id}")
            r.raise_for_status()
            run = r.json()
            s = run.get("status")
            if s != last:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] status: {s}", flush=True)
                last = s
            if s in TERMINAL:
                print(json.dumps(run, ensure_ascii=False, indent=2))
                if s != "completed":
                    sys.exit(1)
                return
            if asyncio.get_event_loop().time() - start > args.timeout:
                print("Timeout", file=sys.stderr)
                sys.exit(1)
            await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
