#!/usr/bin/env python3
"""Start a SciencePal agent run."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx


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
    p = argparse.ArgumentParser(description="Start a SciencePal agent run")
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

    async with _make_client() as c:
        r = await c.post("/agent/initiate", data=data)
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
