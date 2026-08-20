#!/usr/bin/env python3
"""Start a SciencePal agent run.

/agent/initiate provisions a sandbox before it responds, so it is far slower than
every other endpoint here and a client-side timeout on it does NOT mean the run
failed to start. Measured 2026-08-20 on both environments: three calls that raised
httpx.ReadTimeout at the shared 60s client timeout each still created a session
server-side (staging went 153 -> 155 sessions over two timed-out calls, production
118 -> 119 over one). The old behaviour was therefore the worst of both worlds: a
traceback that read as failure, an orphaned run consuming sandbox time, and no
thread_id or agent_run_id printed for the caller to reach it with.

Two changes follow from that. The initiate timeout is raised well above the shared
default, and a timeout that still happens exits with an explicit warning that the
run is probably live and must be located rather than re-requested, because a retry
starts a second run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx

from _spclient import make_client, add_env_arg

# Generous relative to the 60s shared default: sandbox provisioning dominates and is
# not something the client can hurry. Still bounded, so a genuinely wedged request
# surfaces instead of hanging forever.
INITIATE_TIMEOUT = 300.0


async def main() -> None:
    p = argparse.ArgumentParser(description="Start a SciencePal agent run")
    add_env_arg(p)
    p.add_argument("--prompt", "-p", required=True, help="Task prompt")
    p.add_argument("--agent-id", default=None, help="Specific agent ID")
    p.add_argument("--select", default="auto", choices=["manual", "auto"])
    p.add_argument("--no-web-search", action="store_true")
    p.add_argument(
        "--timeout",
        type=float,
        default=INITIATE_TIMEOUT,
        help=f"Seconds to wait for the initiate response (default: {INITIATE_TIMEOUT:g})",
    )
    args = p.parse_args()

    data = {
        "prompt": args.prompt,
        "web_search_on": str(not args.no_web_search).lower(),
        "agent_select_type": args.select,
    }
    if args.agent_id:
        data["agent_id"] = args.agent_id

    async with make_client(args.env, timeout=args.timeout) as c:
        try:
            r = await c.post("/agent/initiate", data=data)
        except httpx.TimeoutException:
            print(
                f"Timed out after {args.timeout:g}s waiting for /agent/initiate on "
                f"{args.env}.\n"
                f"The run has most likely STARTED anyway: this endpoint provisions a "
                f"sandbox before it answers, and the server keeps going after the "
                f"client gives up.\n"
                f"Do NOT re-run this command, which would start a second run. Find the "
                f"new session instead:\n"
                f"  python3 sessions.py --env {args.env}\n"
                f"It is the newest entry, typically in status 'initializing' or "
                f"'running'.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
