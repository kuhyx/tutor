# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``anki_status`` chat kind: what the app's "Sync Anki & credit" polls."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from tutor.anki_collection import COLLECTION_ENV
from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.relay.context import RequestContext

RID = "01J00000000000000000000000"
DEV = "00000000-0000-4000-8000-000000000000"


def _ctx() -> RequestContext:
    return cast("RequestContext", SimpleNamespace(now=lambda: 1_792_000_000.0))


def test_anki_status_is_a_chat_kind_with_no_fields() -> None:
    req = {"kind": "anki_status", "dev": DEV, "created": 1, "body": {"x": 1}}
    got = protocol.validate(RID, req)
    assert (got.lane, got.body) == (protocol.CHAT, {})


def test_anki_status_reports_without_a_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(COLLECTION_ENV, str(tmp_path / "none/collection.anki2"))
    got = asyncio.run(CHAT_HANDLERS["anki_status"](_ctx()))
    assert got == {
        "credited_today_min": 0,
        "eligible_today_min": 0,
        "last_sync_at": None,
        "unavailable": None,
    }


def test_an_unreadable_collection_is_a_retryable_worker_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "collection.anki2"
    path.write_bytes(b"garbage")
    monkeypatch.setenv(COLLECTION_ENV, str(path))
    monkeypatch.setattr("tutor.anki_collection.RETRY_S", 0.0)
    with pytest.raises(RequestError) as caught:
        asyncio.run(CHAT_HANDLERS["anki_status"](_ctx()))
    assert (caught.value.code, caught.value.retry) == ("worker_error", True)
