# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Only the live, running session carries the LeetCode map (display only)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor import guard_route
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._phase import LC, grant
from tutor.tests._relay_support import wiring
from tutor.tests.test_leetcode_projection import WIRE, Mono, _engine, _meta

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.tests._guard_theory import GuardFake


def test_only_the_live_session_carries_the_map(
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
        old = eng.session_id
        await w.publisher.after({old})
        assert _meta(fake, old)["leetcode"] == WIRE
        await eng.start(subject=LC)  # a new live session: `old` is history
        new = eng.session_id
        assert new != old
        await w.publisher.refresh()  # the tick removes the old map
        assert "leetcode" not in _meta(fake, old)
        await w.publisher.session(old, full=True)  # a republish writes none
        assert "leetcode" not in _meta(fake, old)
        await w.publisher.session(new)
        assert _meta(fake, new)["leetcode"] == WIRE
        grant((LC, "b"))  # the phase moved on: no map anywhere, history included
        mono.t += 100
        await w.publisher.refresh()
        assert "leetcode" not in _meta(fake, new)
        assert "leetcode" not in _meta(fake, old)
        await w.rtdb.aclose()

    asyncio.run(go())


def test_a_stopped_session_has_no_map_and_the_tick_leaves_it_so(
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
        assert _meta(fake, sid)["leetcode"] == WIRE
        eng.store.log(sid, {"type": "stop"})
        await w.publisher.session(sid)
        assert _meta(fake, sid)["stopped"] is True
        assert "leetcode" not in _meta(fake, sid)
        mono.t += 100
        asked = len(guard_theory.timeouts)
        await w.publisher.refresh()  # nothing changed on disk: only the tick runs
        assert "leetcode" not in _meta(fake, sid)
        assert len(guard_theory.timeouts) == asked
        await w.rtdb.aclose()

    asyncio.run(go())
