#!/usr/bin/env python3
"""Start a SciencePal agent run. Prints thread_id and agent_run_id."""

from __future__ import annotations

import argparse
import asyncio
import json

from common import make_client


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Start a SciencePal agent run")
    p.add_argument("--prompt", required=True, help="Task prompt")
    p.add_argument("--agent-id", default=None, help="Specific agent ID")
    p.add_argument(
        "--agent-select-type",
        default="auto",
        choices=["manual", "auto"],
        help="Agent selection mode (default: auto)",
    )
    p.add_argument("--no-web-search", action="store_true", help="Disable web search")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    data = {
        "prompt": args.prompt,
        "web_search_on": str(not args.no_web_search).lower(),
        "agent_select_type": args.agent_select_type,
    }
    if args.agent_id:
        data["agent_id"] = args.agent_id

    async with make_client() as client:
        r = await client.post("/agent/initiate", data=data)
        r.raise_for_status()
        result = r.json()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
