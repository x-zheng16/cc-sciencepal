#!/usr/bin/env python3
"""Sandbox file operations: ls, cat, download, upload, rm."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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


async def cmd_ls(args) -> None:
    async with _make_client() as c:
        r = await c.get(f"/sandboxes/{args.sandbox_id}/files", params={"path": args.path})
        r.raise_for_status()
        for f in r.json().get("files", []):
            kind = "d" if f.get("is_dir") else "f"
            print(f"[{kind}] {f['path']}  ({f['size']})")


async def cmd_cat(args) -> None:
    async with _make_client() as c:
        r = await c.get(f"/sandboxes/{args.sandbox_id}/files/content", params={"path": args.path})
        r.raise_for_status()
        sys.stdout.buffer.write(r.content)


async def cmd_download(args) -> None:
    async with _make_client() as c:
        # resolve sandbox_id from thread_id
        r = await c.get(f"/thread/{args.thread_id}/sandbox")
        r.raise_for_status()
        sandbox_id = r.json().get("sandbox_id")
        if not sandbox_id:
            print("No sandbox found for this thread", file=sys.stderr)
            sys.exit(1)

        out = Path(args.output or f"./downloads/{args.thread_id}")
        print(f"sandbox: {sandbox_id}")
        print(f"downloading to: {out}")

        # recursive list
        pending = [args.root]
        files: list[dict] = []
        while pending:
            path = pending.pop()
            r = await c.get(f"/sandboxes/{sandbox_id}/files", params={"path": path})
            r.raise_for_status()
            for entry in r.json().get("files", []):
                if entry.get("is_dir"):
                    pending.append(entry["path"])
                else:
                    files.append(entry)

        # download each file
        count = 0
        for f in files:
            remote = f["path"]
            local = out / remote.lstrip("/")
            local.parent.mkdir(parents=True, exist_ok=True)
            r = await c.get(f"/sandboxes/{sandbox_id}/files/content", params={"path": remote})
            if r.status_code == 200:
                local.write_bytes(r.content)
                count += 1
        print(f"downloaded: {count} files")


async def cmd_upload(args) -> None:
    content = Path(args.local_path).read_bytes()
    async with _make_client() as c:
        r = await c.post(
            f"/sandboxes/{args.sandbox_id}/files",
            data={"path": args.remote_path},
            files={"file": (Path(args.local_path).name, content, "application/octet-stream")},
        )
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))


async def cmd_rm(args) -> None:
    async with _make_client() as c:
        r = await c.request("DELETE", f"/sandboxes/{args.sandbox_id}/files", params={"path": args.path})
        r.raise_for_status()
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(description="Sandbox file operations")
    sub = p.add_subparsers(dest="command", required=True)

    # ls
    ls_p = sub.add_parser("ls", help="List files in a directory")
    ls_p.add_argument("sandbox_id", help="Sandbox ID")
    ls_p.add_argument("path", nargs="?", default="/", help="Directory path (default: /)")

    # cat
    cat_p = sub.add_parser("cat", help="Read a file")
    cat_p.add_argument("sandbox_id", help="Sandbox ID")
    cat_p.add_argument("path", help="File path")

    # download
    dl_p = sub.add_parser("download", help="Download all files from a thread's sandbox")
    dl_p.add_argument("thread_id", help="Thread ID")
    dl_p.add_argument("--output", "-o", default=None, help="Download directory")
    dl_p.add_argument("--root", default="/workspace", help="Sandbox root path")

    # upload
    up_p = sub.add_parser("upload", help="Upload a file")
    up_p.add_argument("sandbox_id", help="Sandbox ID")
    up_p.add_argument("local_path", help="Local file to upload")
    up_p.add_argument("remote_path", help="Destination path in sandbox")

    # rm
    rm_p = sub.add_parser("rm", help="Delete a file")
    rm_p.add_argument("sandbox_id", help="Sandbox ID")
    rm_p.add_argument("path", help="File path to delete")

    args = p.parse_args()
    handlers = {
        "ls": cmd_ls, "cat": cmd_cat, "download": cmd_download,
        "upload": cmd_upload, "rm": cmd_rm,
    }
    asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    main()
