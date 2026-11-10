# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The phone check's loop: a poke ticks early, the interval ticks on its own."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tutor.relay import phone_check
from tutor.tests._interview_support import install
from tutor.tests._phone_support import Rig, interview_fp

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.tests._fake_fp_interview import FakeInterviewFp


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Rig:
    fake: FakeInterviewFp = interview_fp(install(monkeypatch))
    return Rig(tmp_path, fake)


def test_pokes_make_the_loop_tick_early_and_it_keeps_going(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(phone_check, "INTERVAL_S", 30.0)
    monkeypatch.setattr(phone_check, "GAP_S", 0.01)
    ticks: list[int] = []

    async def counted() -> None:
        ticks.append(1)

    monkeypatch.setattr(rig.check, "tick", counted)

    async def go() -> None:
        task = asyncio.create_task(rig.check.run())
        for _ in range(100):
            await asyncio.sleep(0.01)
            if len(ticks) == 1:
                break
        rig.check.poke()
        for _ in range(100):
            await asyncio.sleep(0.01)
            if len(ticks) == 2:
                break
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert len(ticks) == 2


def test_the_loop_also_ticks_on_its_own_interval(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(phone_check, "INTERVAL_S", 0.01)
    monkeypatch.setattr(phone_check, "GAP_S", 0.0)
    ticks: list[int] = []

    async def counted() -> None:
        ticks.append(1)

    monkeypatch.setattr(rig.check, "tick", counted)

    async def go() -> None:
        task = asyncio.create_task(rig.check.run())
        await asyncio.sleep(0.15)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(go())
    assert len(ticks) >= 2
