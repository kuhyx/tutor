# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker's pre-draft loop: idle, Claude up, then queue and sync."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tutor import unavailable
from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.relay import pregen_task, redraft_task
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.pregen_task import PregenWork
from tutor.tests._cur import T0, D, card, module, review, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import engine, wiring

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

NOW_S = (T0 + 30 * D) / 1000


def _work(tmp_path: Path, busy: list[bool]) -> tuple[PregenWork, Any]:
    eng, _ = engine(tmp_path)
    w = wiring(FakeRtdb(), eng, now=lambda: NOW_S)
    mods = [module("a", status="ready", cards=1), module("b", "a"), module("c", "b")]
    subject(eng.ctx, modules=mods, found={"a-1": card("a", 1)})
    review(eng.ctx, "car", "a-1", T0 + 29 * D, 3)
    return PregenWork(w, CurriculumSync(w), lambda: busy[0]), eng


def _status(eng: Any, mid: str) -> tuple[str, bool]:
    plan = eng.ctx.subjects.plan("car")
    found = plan.module(mid)
    return found.status, found.pregenerated


def test_an_idle_round_queues_the_next_module_for_the_build_lane(
    tmp_path: Path,
) -> None:
    busy = [True]
    work, eng = _work(tmp_path, busy)

    async def go() -> list[str]:
        got = [await work.once()]
        busy[0] = False
        got += [await work.once(), await work.once()]
        await work.w.rtdb.aclose()
        return got

    assert asyncio.run(go()) == ["busy", "queued", "idle"]
    assert _status(eng, "b") == ("generating", True)
    assert _status(eng, "c") == ("locked", False)
    assert work.curriculum.queue.qsize() == 1
    assert work.curriculum.queue.get_nowait() == ("car", "b")


def test_an_outage_window_skips_the_round(tmp_path: Path) -> None:
    work, eng = _work(tmp_path, [False])
    unavailable.record("rate_limit", NOW_S - 60, NOW_S + 3600)

    async def go() -> str:
        got = await work.once()
        await work.w.rtdb.aclose()
        return got

    assert asyncio.run(go()) == "unavailable"
    assert _status(eng, "b") == ("locked", False)


def test_switched_off_with_card_work_it_never_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, _ = _work(tmp_path, [False])
    rounds: list[int] = []

    async def once() -> str:
        rounds.append(1)
        return "idle"

    monkeypatch.setattr(work, "once", once)
    monkeypatch.setenv(redraft_task.SWITCH_ENV, "off")
    asyncio.run(asyncio.wait_for(work.run(), 5))
    assert rounds == []


def test_a_failed_round_is_logged_and_the_loop_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    work, _ = _work(tmp_path, [False])
    rounds: list[int] = []

    async def once() -> str:
        rounds.append(1)
        if len(rounds) == 1:
            msg = "plan changed"
            raise RequestError(BAD_REQUEST, msg)
        work.stopped = True
        return "idle"

    monkeypatch.setattr(work, "once", once)
    monkeypatch.setattr(pregen_task, "PERIOD_S", 0.0)
    monkeypatch.delenv(redraft_task.SWITCH_ENV, raising=False)
    asyncio.run(asyncio.wait_for(work.run(), 5))
    assert rounds == [1, 1]
    assert "pre-draft round failed" in caplog.text
