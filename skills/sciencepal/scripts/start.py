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

The two cases are kept apart, because the advice inverts between them. If the request
was sent, the outcome is unknowable and the caller must NOT retry (exit 2). If it
never left this process, nothing started and a retry is safe (exit 3). Catching
httpx.TimeoutException as one thing would tell someone whose network is down to go
hunting for a session that was never created; the partition here is by whether a
connection was established, not by whether the failure was a timeout, because a
server that hangs up without answering is as ambiguous as one that answers late.
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
        except (httpx.ConnectTimeout, httpx.ConnectError, httpx.PoolTimeout) as exc:
            # The request never left this process, so nothing started server-side and a
            # retry is safe. Saying otherwise would send the caller hunting sessions.py
            # for a session that does not exist, which is the opposite of the fix.
            print(
                f"Could not reach the {args.env} API: {type(exc).__name__}.\n"
                f"The request never left this machine, so no run was started and it is "
                f"safe to retry once connectivity is back.",
                file=sys.stderr,
            )
            raise SystemExit(3)
        except httpx.TransportError:
            # Everything else that can go wrong at the transport layer once the
            # connection exists: read and write timeouts, and a server that hangs up
            # without answering. In all of them the request was sent and whether the
            # server acted on it is unknowable here. It usually did.
            print(
                f"No usable response from /agent/initiate on {args.env} "
                f"(waited up to {args.timeout:g}s).\n"
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
