# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``meta/busy`` always clears: errors, cancellation, failed clears, restarts.

A stuck ``busy`` disables Send in the app for good, so every way a request
can end (or a process can die) must leave it cleared, if not at once then
on the next idle sweep.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay import worker
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.claims import Claim
from tutor.relay.phases import PhaseSink
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, engine, request, server, wiring

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.engine import Engine
    from tutor.relay.lanes import Server

SID = "20200101-000000-abcd"
BUSY = f"tutor/v1/sessions/{SID}/meta/busy"
STALE = {"rid": RIDS[29], "phase": "thinking", "since": 1, "text": "x"}


class UnexpectedBugError(Exception):
    """Not an error a handler may report: a bug."""


async def _until(check: Any, tries: int = 500) -> None:
    for _ in range(tries):
        if check():
            return
        await asyncio.sleep(0.001)
    raise AssertionError


def _rig(eng: Engine) -> tuple[FakeRtdb, Server]:
    fake = FakeRtdb()
    return fake, server(wiring(fake, eng))


async def _serve(srv: Server, n: int = 0) -> Any:
    req = request("stop", {"session": SID})
    return await srv.serve(RIDS[n], req, "chat")


def test_busy_clears_when_the_handler_raises_a_bug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake, srv = _rig(eng)

    async def broken(_ctx: object) -> dict[str, Any]:
        await _until(lambda: fake.get(BUSY) is not None)
        raise UnexpectedBugError

    monkeypatch.setitem(CHAT_HANDLERS, "stop", broken)

    async def go() -> None:
        with pytest.raises(UnexpectedBugError):
            await _serve(srv)
        assert fake.get(BUSY) is None
        await srv.w.rtdb.aclose()

    asyncio.run(go())


def test_busy_clears_when_the_request_is_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake, srv = _rig(eng)

    async def forever(_ctx: object) -> dict[str, Any]:
        await asyncio.Event().wait()
        return {}

    monkeypatch.setitem(CHAT_HANDLERS, "stop", forever)

    async def go() -> None:
        task = asyncio.create_task(_serve(srv))
        await _until(lambda: fake.get(BUSY) is not None)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert fake.get(BUSY) is None
        await srv.w.rtdb.aclose()

    asyncio.run(go())


def test_a_failed_clear_is_swept_once_idle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake, srv = _rig(eng)

    async def offline(_ctx: object) -> dict[str, Any]:
        await _until(lambda: fake.get(BUSY) is not None)
        fake.fail[("PATCH", f"/sessions/{SID}/meta")] = 503  # the clear fails
        return {}

    monkeypatch.setitem(CHAT_HANDLERS, "stop", offline)

    async def go() -> None:
        assert (await _serve(srv))["ok"]
        assert fake.get(BUSY) is not None
        await srv.sweep_busy()  # still offline: kept for the next sweep
        assert srv.stale_busy == {SID}
        fake.fail.clear()
        srv.current["build"] = "01M4RBCX52MMHCK7K73E6KV999"
        await srv.sweep_busy()  # a reply in flight: leave busy alone
        assert fake.get(BUSY) is not None
        srv.current["build"] = None
        await srv.sweep_busy()
        assert fake.get(BUSY) is None
        writes = len(fake.log)
        await srv.sweep_busy()  # nothing left to clear: no traffic
        assert len(fake.log) == writes
        await srv.w.rtdb.aclose()

    asyncio.run(go())


def test_busy_left_by_a_previous_process_is_cleared(tmp_path: Path) -> None:
    """The flag is cleared even if this claim never wrote it itself."""
    eng, _ = engine(tmp_path)
    fake, srv = _rig(eng)

    async def go() -> None:
        fake.set(BUSY, STALE)
        claim = Claim(srv.w.rtdb, RIDS[0], "w1", eng.time)
        claim.busy_session = SID
        assert await claim.clear_busy()
        assert fake.get(BUSY) is None
        await srv.w.rtdb.aclose()

    asyncio.run(go())


def test_startup_clears_busy_on_the_live_session(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))
    fake = FakeRtdb()

    async def go() -> None:
        srv = server(wiring(fake, eng))
        req = request("session_start", {"subject": None, "card": None})
        sid = (await srv.serve(RIDS[0], req, "chat") or {})["data"]["session"]
        await srv.w.rtdb.aclose()
        busy = f"tutor/v1/sessions/{sid}/meta/busy"
        fake.set(busy, STALE)  # the old process died mid-reply
        relay = worker.Relay(eng, fake.rtdb(), PhaseSink(), eng.time)
        await relay._startup()
        assert fake.get(busy) is None
        await relay.w.rtdb.aclose()

    asyncio.run(go())
