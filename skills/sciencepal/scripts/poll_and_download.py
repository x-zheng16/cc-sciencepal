#!/usr/bin/env python3
"""Poll agent run status until terminal, then download sandbox files."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from common import TERMINAL_STATUSES, download_sandbox_files, make_client


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Poll SciencePal run and download results")
    p.add_argument("--agent-run-id", required=True)
    p.add_argument("--thread-id", required=True, help="Thread ID (to resolve sandbox)")
    p.add_argument("--output-dir", default=None, help="Download directory")
    p.add_argument("--poll-interval", type=float, default=10)
    p.add_argument("--timeout", type=float, default=3600)
    p.add_argument("--root", default="/workspace", help="Sandbox root path to download")
    p.add_argument("--status-file", default=None, help="Write final status to this file")
    p.add_argument("--no-download", action="store_true", help="Skip file download")
    return p.parse_args()


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


async def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or f"./downloads/{args.agent_run_id}"

    log(f"Polling agent_run_id={args.agent_run_id}")

    async with make_client() as client:
        start = asyncio.get_event_loop().time()
        last_status = None

        while True:
            r = await client.get(f"/agent-run/{args.agent_run_id}")
            r.raise_for_status()
            run = r.json()
            status = run.get("status")

            if status != last_status:
                log(f"Status: {status}")
                last_status = status

            if status in TERMINAL_STATUSES:
                break

            elapsed = asyncio.get_event_loop().time() - start
            if elapsed >= args.timeout:
                log(f"Timeout after {args.timeout}s")
                sys.exit(1)

            await asyncio.sleep(args.poll_interval)

        if status != "completed":
            log(f"Run ended: {status} (error: {run.get('error', 'N/A')})")
            sys.exit(1)

        log("Run completed")

        if args.no_download:
            print(json.dumps(run, ensure_ascii=False, indent=2))
            return

        # Resolve sandbox_id from thread_id
        log("Resolving sandbox_id from thread...")
        r = await client.get(f"/thread/{args.thread_id}/sandbox")
        r.raise_for_status()
        sandbox_info = r.json()
        sandbox_id = sandbox_info.get("sandbox_id")
        if not sandbox_id:
            log("No sandbox_id found for this thread")
            print(json.dumps(run, ensure_ascii=False, indent=2))
            return

        log(f"sandbox_id={sandbox_id}, downloading to {output_dir}")
        downloaded = await download_sandbox_files(
            client, sandbox_id, output_dir, root=args.root,
        )
        log(f"Downloaded {len(downloaded)} files")

        result = {
            "agent_run_id": args.agent_run_id,
            "thread_id": args.thread_id,
            "sandbox_id": sandbox_id,
            "status": "completed",
            "downloaded_count": len(downloaded),
            "output_dir": str(Path(output_dir).resolve()),
            "files": downloaded[:20],
        }
        if args.status_file:
            Path(args.status_file).parent.mkdir(parents=True, exist_ok=True)
            Path(args.status_file).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
