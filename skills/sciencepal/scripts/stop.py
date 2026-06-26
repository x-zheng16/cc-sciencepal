#!/usr/bin/env python3
"""Stop a running SciencePal agent run."""
from __future__ import annotations

import argparse
import asyncio
import json

from _spclient import make_client, add_env_arg


async def main() -> None:
    p = argparse.ArgumentParser(description="Stop a SciencePal agent run")
    add_env_arg(p)
    p.add_argument("agent_run_id", help="agent_run_id to stop")
    args = p.parse_args()

    async with make_client(args.env) as c:
        r = await c.post(f"/agent-run/{args.agent_run_id}/stop")
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
