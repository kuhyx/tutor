# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Who spends the carry-over bank (only the live worker) and what stats show."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor import carry, credit, leftover, review_credit
from tutor.clock import BlockReady
from tutor.curriculum.stats import stats
from tutor.relay import curriculum_sync, worker
from tutor.relay.phases import PhaseSink
from tutor.tests._cur import make_ctx
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import ManualClock
from tutor.tests._relay_support import engine, wiring
from tutor.tests.test_carry import at, carry_rows, own

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_stats_show_banked_and_prepaid_without_spending(tmp_path: Path) -> None:
    own(23, 70)  # quota 30: 40 banked
    ctx, fakes = make_ctx(tmp_path / "data")
    fakes.now[0] = int(at(23, 20) * 1000)
    today = stats(ctx)["today"]
    assert (today["banked"], today["prepaid"]) == (40, 0)
    fakes.now[0] = int(at(24, 9) * 1000)
    today = stats(ctx)["today"]
    assert (today["banked"], today["prepaid"]) == (40, 0)  # read-only: no spend
    assert carry_rows() == []
    carry.spend(now=at(24, 9))
    today = stats(ctx)["today"]
    assert (today["banked"], today["prepaid"]) == (0, 40)


def test_the_publisher_spends_before_it_builds_stats(tmp_path: Path) -> None:
    own(23, 50)  # 20 banked
    eng, _ = engine(tmp_path, clock=ManualClock(at(24, 9)))
    eng.ctx.clock = lambda: int(at(24, 9) * 1000)
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await w.publisher.stats()
        await w.rtdb.aclose()

    asyncio.run(go())
    assert [r["entry_id"] for r in carry_rows()] == ["carry-2026-10-24-m20"]
    assert fake.get("tutor/v1-e2e/stats/today/prepaid") == 20
    assert fake.get("tutor/v1-e2e/stats/today/banked") == 0


def test_the_curriculum_tick_spends_after_review_credit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        review_credit,
        "credit_now",
        lambda *_a, **_k: calls.append("review"),
    )
    monkeypatch.setattr(carry, "spend", lambda **_k: calls.append("carry"))
    eng, _ = engine(tmp_path, clock=ManualClock(at(24, 9)))
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await curriculum_sync.CurriculumSync(w).sync()
        await w.rtdb.aclose()

    asyncio.run(go())
    assert calls == ["review", "carry"]


def test_the_curriculum_tick_pays_recent_leftover_before_carry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(review_credit, "credit_now", lambda *_a, **_k: None)
    monkeypatch.setattr(
        leftover, "pay", lambda folder, **k: calls.append((folder.name, k["days"]))
    )
    monkeypatch.setattr(carry, "spend", lambda **_k: calls.append("carry"))
    eng, _ = engine(tmp_path, clock=ManualClock(at(24, 9)))
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        await curriculum_sync.CurriculumSync(w).sync()
        await w.rtdb.aclose()

    asyncio.run(go())
    assert calls == [("sessions", ["20261023", "20261024"]), "carry"]


def test_startup_pays_every_days_leftover_before_carry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(
        leftover, "pay", lambda folder, **k: calls.append((folder.name, k["days"]))
    )
    monkeypatch.setattr(carry, "spend", lambda **_k: calls.append("carry"))
    eng, _ = engine(tmp_path, clock=ManualClock(at(24, 9)))
    fake = FakeRtdb()

    async def go() -> None:
        relay = worker.Relay(eng, fake.rtdb(), PhaseSink(), eng.time)
        await relay._carry()
        await relay.w.rtdb.aclose()

    asyncio.run(go())
    assert calls == [("sessions", None), "carry"]


def test_stats_show_todays_own_and_leetcode_minutes_apart_from_carry(
    tmp_path: Path,
) -> None:
    """kuhy, 2026-11-26: reviews paid, but carry had filled 15/15 so nothing moved.

    ``own_minutes`` counts today's own ``credit`` minutes (never a carry row),
    ``lc_minutes`` today's ``leetcode_theory`` ones (part e79be0be-1).
    """
    own(23, 70)  # Friday: 40 banked for Saturday
    ctx, fakes = make_ctx(tmp_path / "data")
    carry.spend(now=at(24, 9))  # Saturday's carry row
    fakes.now[0] = int(at(24, 12) * 1000)
    today = stats(ctx)["today"]
    assert (today["own_minutes"], today["lc_minutes"]) == (0, 0)
    own(24, 3, hour=11, tag="beef")
    last = BlockReady(2, 120.0, at(24, 11, 30), 0, 0)
    lc = "leetcode-easy-algorithms-in-typescript"
    assert credit.credit_span(
        last, 2, "lc-run", now=at(24, 11, 30), subject=lc
    ).recorded
    today = stats(ctx)["today"]
    assert (today["own_minutes"], today["lc_minutes"]) == (3, 2)
