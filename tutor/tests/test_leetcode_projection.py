# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The LeetCode bar's map in a session's published meta (display only).

``sessions/{sid}/meta/leetcode`` exists for a LeetCode theory session only. It
is refreshed when the session is published (start, open, after each turn) and
on the worker's tick at most once a minute, so a credit the guard mints
after a turn shows without a new learner turn.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tutor import guard_route, history
from tutor.engine import Engine
from tutor.relay import views
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests._guard_theory import GuardFake, theory
from tutor.tests._phase import LC, grant, write_phase
from tutor.tests._relay_support import wiring

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

WIRE = {
    "unit": "a",
    "taught": 0,
    "total": 2,
    "full": False,
    "into": 7,
    "per_credit": 12,
    "credits": 0,
    "needed": 7,
}


class Mono:
    """The publisher's monotonic clock, moved by the test."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _engine(root: Path, *replies: Any) -> Engine:
    ctx, _ = make_ctx(root)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {"a0": card("a", 0), "a1": card("a", 1), "b0": card("b", 0)}
    subject(ctx, LC, modules=mods, found=found)
    return Engine(
        store=Store(root),
        now=ManualClock(),
        session_factory=lambda _p: FakeSession(*(replies or (turn(),) * 4)),
    )


def _meta(fake: FakeRtdb, sid: str) -> dict[str, Any]:
    meta: dict[str, Any] = fake.get(f"tutor/v1-e2e/sessions/{sid}/meta")
    return meta


def _src(eng: Engine, found: Any) -> views.Sources:
    view = history.View({c.id: c.front for c in eng.deck}, eng.session_id, set(), set())
    return views.Sources(
        view, eng.time(), lambda _r: None, lambda _p: None, None, found
    )


def test_build_adds_the_map_only_when_there_is_one(tmp_path: Path) -> None:
    grant((LC, "a"))
    eng = _engine(tmp_path)
    asyncio.run(eng.start(subject=LC))
    asked: list[tuple[str, str]] = []

    def found(subj: str, cid: str) -> dict[str, Any]:
        asked.append((subj, cid))
        return {"unit": "a"}

    doc = views.build(eng.store.root / "sessions", eng.session_id, _src(eng, found))
    assert doc is not None
    assert doc.meta["leetcode"] == {"unit": "a"}
    assert asked == [(LC, "a0")]
    plain = views.build(
        eng.store.root / "sessions", eng.session_id, _src(eng, lambda *_: None)
    )
    assert plain is not None
    assert "leetcode" not in plain.meta
    unwired = views.build(eng.store.root / "sessions", eng.session_id, _src(eng, None))
    assert unwired is not None
    assert "leetcode" not in unwired.meta


def test_a_theory_session_publishes_the_map_and_an_ordinary_one_none(
    tmp_path: Path, guard_theory: GuardFake
) -> None:
    grant((LC, "a"))
    eng = _engine(tmp_path)
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await eng.start(subject=LC)
        sid = eng.session_id
        await w.publisher.after({sid})
        assert _meta(fake, sid)["leetcode"] == WIRE
        grant((LC, "b"))  # the unit moved on
        await w.publisher.session(sid)
        assert "leetcode" not in _meta(fake, sid)  # the stale map is gone
        await w.rtdb.aclose()

    asyncio.run(go())


def test_no_phase_file_publishes_no_map_and_asks_no_one(
    tmp_path: Path, guard_theory: GuardFake
) -> None:
    grant((LC, "a"))
    eng = _engine(tmp_path)
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await eng.start(subject=LC)
        write_phase(None).unlink()  # the guard's file is gone
        await w.publisher.after({eng.session_id})
        assert "leetcode" not in _meta(fake, eng.session_id)
        await w.rtdb.aclose()

    asyncio.run(go())
    assert guard_theory.timeouts == []


def test_the_tick_asks_again_once_a_minute_and_replaces_the_map(
    tmp_path: Path, guard_theory: GuardFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant((LC, "a"))
    eng = _engine(tmp_path)
    fake = FakeRtdb()
    mono = Mono()

    async def go() -> None:
        w = wiring(fake, eng)
        w.publisher._lc.mono = mono
        monkeypatch.setattr(guard_route, "clock", mono)
        await eng.start(subject=LC)
        sid = eng.session_id
        await w.publisher.after({sid})
        assert len(guard_theory.timeouts) == 1
        guard_theory.reply = theory(credits_today=1, minutes_into_credit=0, needed=12)
        mono.t += 59
        await w.publisher.refresh()
        assert len(guard_theory.timeouts) == 1  # too soon
        assert _meta(fake, sid)["leetcode"]["credits"] == 0
        mono.t += 2
        await w.publisher.refresh()
        assert len(guard_theory.timeouts) == 2
        assert _meta(fake, sid)["leetcode"] == WIRE | {
            "credits": 1,
            "into": 0,
            "needed": 12,
        }
        guard_theory.reply = OSError("down")  # a number lost is left out, not 0
        mono.t += 61
        await w.publisher.refresh()
        assert _meta(fake, sid)["leetcode"] == {
            k: v
            for k, v in WIRE.items()
            if k not in {"into", "per_credit", "credits", "needed"}
        }
        fake.log.clear()
        mono.t += 61
        await w.publisher.refresh()  # the same map again: nothing written
        assert all("leetcode" not in p for _, p in fake.log)
        await w.rtdb.aclose()

    asyncio.run(go())


def test_the_tick_drops_the_map_when_the_phase_ends(
    tmp_path: Path, guard_theory: GuardFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant((LC, "a"))
    eng = _engine(tmp_path)
    fake = FakeRtdb()
    mono = Mono()

    async def go() -> None:
        w = wiring(fake, eng)
        w.publisher._lc.mono = mono
        monkeypatch.setattr(guard_route, "clock", mono)
        await eng.start(subject=LC)
        sid = eng.session_id
        await w.publisher.after({sid})
        grant((LC, "b"))
        mono.t += 61
        await w.publisher.refresh()
        assert "leetcode" not in _meta(fake, sid)
        await w.rtdb.aclose()

    asyncio.run(go())


def test_the_tick_does_nothing_without_a_live_card(tmp_path: Path) -> None:
    eng = _engine(tmp_path)
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await w.publisher.refresh()
        assert guard_route.GUARD_THEORY_URL not in str(fake.log)
        await w.rtdb.aclose()

    asyncio.run(go())
