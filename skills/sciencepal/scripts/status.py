#!/usr/bin/env python3
"""Check or wait for agent run status."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

TERMINAL = {"completed", "failed", "stopped"}


def _make_client() -> httpx.AsyncClient:
    env_path = Path.home() / ".claude" / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v
    token = os.getenv("SCIENCEPAL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Missing SCIENCEPAL_ACCESS_TOKEN")
    base_url = os.getenv("SCIENCEPAL_BASE_URL", "https://sciencepal.ai/api")
    for k in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )


async def main() -> None:
    p = argparse.ArgumentParser(description="Check or wait for agent run status")
    p.add_argument("agent_run_id", help="Agent run ID")
    p.add_argument("--wait", "-w", action="store_true", help="Poll until complete")
    p.add_argument("--interval", "-i", type=float, default=10, help="Poll interval (seconds)")
    p.add_argument("--timeout", type=float, default=3600, help="Max wait time (seconds)")
    args = p.parse_args()

    async with _make_client() as c:
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
