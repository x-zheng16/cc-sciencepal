"""SciencePal API client -- thin httpx wrapper, no SDK dependency."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

ENV_PATH = Path.home() / ".claude" / ".env"
BASE_URL_DEFAULT = "https://sciencepal.ai/api"
TERMINAL_STATUSES = {"completed", "failed", "stopped"}


def load_env() -> None:
    """Load env vars from ~/.claude/.env without overriding existing ones."""
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_token() -> str:
    load_env()
    token = os.getenv("SCIENCEPAL_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("Missing SCIENCEPAL_ACCESS_TOKEN in env or ~/.claude/.env")
    return token


def get_base_url() -> str:
    load_env()
    return os.getenv("SCIENCEPAL_BASE_URL", BASE_URL_DEFAULT)


def make_client() -> httpx.AsyncClient:
    for k in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)
    return httpx.AsyncClient(
        base_url=get_base_url(),
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=60.0,
    )


async def list_sandbox_files(
    client: httpx.AsyncClient, sandbox_id: str, root: str = "/",
) -> list[dict]:
    """Recursively list all files in a sandbox."""
    pending = [root]
    files: list[dict] = []
    while pending:
        path = pending.pop()
        r = await client.get(f"/sandboxes/{sandbox_id}/files", params={"path": path})
        r.raise_for_status()
        for entry in r.json().get("files", []):
            if entry.get("is_dir"):
                pending.append(entry["path"])
            else:
                files.append(entry)
    return files


async def download_sandbox_files(
    client: httpx.AsyncClient,
    sandbox_id: str,
    output_dir: str,
    root: str = "/workspace",
) -> list[str]:
    """Download all files from a sandbox to a local directory."""
    files = await list_sandbox_files(client, sandbox_id, root=root)
    downloaded: list[str] = []
    base = Path(output_dir)
    for f in files:
        remote = f["path"]
        local = base / remote.lstrip("/")
        local.parent.mkdir(parents=True, exist_ok=True)
        r = await client.get(
            f"/sandboxes/{sandbox_id}/files/content",
            params={"path": remote},
        )
        if r.status_code == 200:
            local.write_bytes(r.content)
            downloaded.append(str(local))
    return downloaded
