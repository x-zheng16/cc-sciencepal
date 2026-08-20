"""The follow-up insert must prove its row landed, not assume it.

`insert_user_message` reads the inserted row back (`Prefer: return=representation`)
and refuses anything that is not exactly one matching row. These tests pin every
refusal, because the value of the check is entirely in the paths that fail: a 2xx
carrying the wrong row would otherwise reach the start endpoint, which resolves
its target by taking the newest human user row on the thread and would therefore
act on the wrong message while reporting success.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "sciencepal" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from followup import _parse_inserted_message_id  # noqa: E402

THREAD = "66ca0007-c926-44b5-b8c8-829cc2a4f41c"
MESSAGE = "2515274b-4c7f-4782-b03e-3b17fecad171"


def _response(payload: str, status: int = 201) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        content=payload.encode(),
        headers={"Content-Type": "application/json"},
        request=httpx.Request("POST", "https://example.supabase.co/rest/v1/messages"),
    )


def test_accepts_exactly_one_matching_row() -> None:
    body = f'[{{"message_id":"{MESSAGE}","thread_id":"{THREAD}","type":"user"}}]'
    assert _parse_inserted_message_id(_response(body), THREAD) == MESSAGE


def test_rejects_a_non_json_representation() -> None:
    with pytest.raises(SystemExit, match="non-JSON representation"):
        _parse_inserted_message_id(_response("not json at all"), THREAD)


def test_rejects_an_empty_representation() -> None:
    # `Prefer: return=minimal` behaviour reaching this parser, or an insert that
    # RLS silently filtered to zero rows, both arrive as an empty array.
    with pytest.raises(SystemExit, match="exactly one inserted row"):
        _parse_inserted_message_id(_response("[]"), THREAD)


def test_rejects_more_than_one_row() -> None:
    row = f'{{"message_id":"{MESSAGE}","thread_id":"{THREAD}","type":"user"}}'
    with pytest.raises(SystemExit, match="exactly one inserted row"):
        _parse_inserted_message_id(_response(f"[{row},{row}]"), THREAD)


def test_rejects_an_object_instead_of_an_array() -> None:
    body = f'{{"message_id":"{MESSAGE}","thread_id":"{THREAD}","type":"user"}}'
    with pytest.raises(SystemExit, match="exactly one inserted row"):
        _parse_inserted_message_id(_response(body), THREAD)


def test_rejects_a_malformed_row() -> None:
    with pytest.raises(SystemExit, match="malformed row"):
        _parse_inserted_message_id(_response('["just a string"]'), THREAD)


def test_rejects_a_row_that_landed_on_another_thread() -> None:
    body = (
        f'[{{"message_id":"{MESSAGE}",'
        f'"thread_id":"00000000-0000-0000-0000-000000000000","type":"user"}}]'
    )
    with pytest.raises(SystemExit, match="does not match what was asked for"):
        _parse_inserted_message_id(_response(body), THREAD)


def test_rejects_a_row_of_the_wrong_type() -> None:
    # `status` rows exist on real threads and are NOT what the start endpoint
    # looks for, so one inserted by mistake would be silently skipped.
    body = f'[{{"message_id":"{MESSAGE}","thread_id":"{THREAD}","type":"status"}}]'
    with pytest.raises(SystemExit, match="does not match what was asked for"):
        _parse_inserted_message_id(_response(body), THREAD)


@pytest.mark.parametrize("value", ['""', '"   "', "null", "123"])
def test_rejects_a_missing_or_blank_message_id(value: str) -> None:
    body = f'[{{"message_id":{value},"thread_id":"{THREAD}","type":"user"}}]'
    with pytest.raises(SystemExit, match="carries no message_id"):
        _parse_inserted_message_id(_response(body), THREAD)


def test_the_returned_id_is_not_sent_to_the_start_endpoint() -> None:
    """The id is diagnostic. Pin that the client never tries to correlate with it.

    `AgentStartRequest` declares 10 properties and neither `message_id` nor
    `idempotency_key` is among them; Pydantic drops unknown JSON keys, so sending
    one would look exactly like success while doing nothing. Guard the regression
    by reading the source, since the wire call itself needs a live thread.
    """
    source = (SCRIPTS / "followup.py").read_text()
    # Anchor on the call itself, not on the prose above it that names the endpoint.
    marker = 'c.post(f"/thread/{args.thread}/agent/start"'
    assert source.count(marker) == 1
    start_call = source.split(marker, 1)[1]
    assert start_call.startswith(", json={})")
    assert "message_id" not in start_call.split("r.raise_for_status", 1)[0]
