#!/usr/bin/env python3
"""Start a SciencePal agent run."""

from __future__ import annotations

import argparse
import asyncio
import json
from _spclient import make_client, add_env_arg


async def main() -> None:
    p = argparse.ArgumentParser(description="Start a SciencePal agent run")
    add_env_arg(p)
    p.add_argument("--prompt", "-p", required=True, help="Task prompt")
    p.add_argument("--agent-id", default=None, help="Specific agent ID")
    p.add_argument("--select", default="auto", choices=["manual", "auto"])
    p.add_argument("--no-web-search", action="store_true")
    args = p.parse_args()

    data = {
        "prompt": args.prompt,
        "web_search_on": str(not args.no_web_search).lower(),
        "agent_select_type": args.select,
    }
    if args.agent_id:
        data["agent_id"] = args.agent_id

    async with make_client(args.env) as c:
        r = await c.post("/agent/initiate", data=data)
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
