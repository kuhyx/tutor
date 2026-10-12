# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Edge branches: odd SSE events, odd transcript lines, startup prepare, lanes."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, cast

from tutor.relay import cli, sse, views
from tutor.relay.inbox import Inbox
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, engine, request, server, wiring

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    import pytest

    from tutor.engine import Engine
    from tutor.relay.rtdb import Rtdb


class _Lines:
    """An Rtdb stand-in whose one stream yields fixed SSE lines."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    async def open_stream(self, path: str, params: Any = None) -> AsyncIterator[str]:
        del path, params
        for line in self.lines:
            yield line


def test_unknown_events_are_skipped() -> None:
    lines = [
        "event: keep-alive",
        "data: null",
        "",
        "",
        "event: put",
        'data: {"data": 1}',
        "",
    ]

    async def go() -> list[sse.Event]:
        return [
            e async for e in sse._one_connection(cast("Rtdb", _Lines(lines)), "p", None)
        ]

    assert asyncio.run(go()) == [sse.Event("put", "/", 1)]


def test_non_object_transcript_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "s.jsonl"
    path.write_text('[1]\n{"type": "start"}\n')
    assert views._events(path) == [{"type": "start"}]


def test_resume_session_with_nothing_live(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("A?"))

    async def go() -> None:
        await eng.start()
        sid = eng.session_id
        eng._session, eng._conv, eng.card = None, None, None  # a fresh process
        await eng.resume_session(eng.store.root / "sessions" / f"{sid}.jsonl")
        assert eng.session_id == sid

    asyncio.run(go())


class _Prepared:
    session_id = "20261012-000000-abcd"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def repair_done_cards(self) -> list[tuple[str, str]]:
        return [("card-a", "s1")]

    def backfill_today(self) -> None:
        self.calls.append("backfill")

    def resume_latest(self) -> bool:
        self.calls.append("resume")
        return True


def test_prepare_logs_repairs_and_resume(caplog: pytest.LogCaptureFixture) -> None:
    eng = _Prepared()
    with caplog.at_level(logging.WARNING):
        cli.prepare(cast("Engine", eng), fresh=False)
    assert "marked card-a done from s1" in caplog.text
    assert "resumed session 20261012-000000-abcd" in caplog.text
    fresh = _Prepared()
    cli.prepare(cast("Engine", fresh), fresh=True)
    assert fresh.calls == ["backfill"]


def test_lane_skips_a_request_held_elsewhere(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        box = Inbox(w, server(w))
        held = {"by": "other", "lease_until": 10**15}
        fake.set(f"tutor/v1/requests/{RIDS[0]}/claim", held)
        box.tree = {RIDS[0]: {"req": request("stop", {})}}
        box.queued.add(RIDS[0])
        await box.queues["chat"].put(RIDS[0])
        task = asyncio.create_task(box.lane("chat"))
        await asyncio.sleep(0.05)
        task.cancel()
        assert "result" not in box.tree[RIDS[0]]
        assert RIDS[0] not in box.queued
        await w.rtdb.aclose()

    asyncio.run(go())
