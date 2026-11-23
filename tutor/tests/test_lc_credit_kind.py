# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A GATED (LeetCode) subject's minutes are ``leetcode_theory`` rows, not ``credit``.

kuhy, 2026-11-23: LeetCode lessons in the tutor paid the next day's tutor
bonus through the carry bank. Their rows now carry
:data:`tutor.ledger_pay.LC_CREDIT`: leetcode-guard pays them as theory
minutes, earned_time's tutor earner and the carry bank never see them, and
the tutor's own "already paid" check still does (exactly once).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import earned_time

from tutor import carry, credit, ledger_pay, progress, unit_credit
from tutor.clock import BlockReady
from tutor.engine import Engine
from tutor.ledger_io import default_paths
from tutor.store import Store
from tutor.tests._credit_support import NOON, ZONE, entries, unit
from tutor.tests._cur import T0, card, make_ctx, module, subject
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock, turn
from tutor.tests._phase import LC, grant
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path

LESSON = ledger_pay.Taught(subject=LC, module="a")
DAY = date(2026, 10, 9)  # NOON's local day, a Friday (quota 30)


def _rows() -> list[dict[str, Any]]:
    return entries(default_paths())


def _teach(root: Path, **kw: Any) -> Engine:
    """LC (``c0`` in module ``a``, granted by C3): 3 long answers on ``c0``."""
    grant((LC, "a"))
    ctx, _ = make_ctx(root)
    found = {"c0": card("a", 0), "c1": card("b", 1)}
    mods = [module(m, status="ready", cards=1) for m in ("a", "b")]
    subject(ctx, LC, modules=mods, found=found)
    clock = ManualClock(T0 / 1000)
    fake = FakeSession(*[turn() for _ in range(4)])
    engine = Engine(store=Store(root), now=clock, session_factory=lambda _p: fake, **kw)
    asyncio.run(engine.start("c0", subject=LC))
    for i in range(3):
        clock.advance(170)
        asyncio.run(engine.reply("the answer, at length", msg_id=f"m{i}"))
    return engine


def test_kind_for_names_only_gated_subjects_leetcode() -> None:
    assert ledger_pay.kind_for(LC) == ledger_pay.LC_CREDIT
    assert ledger_pay.kind_for("car") == ledger_pay.CREDIT
    assert ledger_pay.kind_for(None) == ledger_pay.CREDIT


def test_a_gated_span_is_paid_exactly_once_across_ticks() -> None:
    first = unit_credit.credit_units(
        [unit(n) for n in (1, 2, 3)], "s", now=NOON, taught=LESSON
    )
    assert [r["entry_id"] for r in first if r["recorded"]] == ["s-m3"]
    later = unit_credit.credit_units(
        [unit(n) for n in range(1, 6)], "s", now=NOON, taught=LESSON
    )
    assert [(r["entry_id"], r["minutes"]) for r in later] == [("s-m5", 2)]
    for _ in range(3):  # every later tick finds all five minutes paid
        assert (
            unit_credit.credit_units(
                [unit(n) for n in range(1, 6)], "s", now=NOON, taught=LESSON
            )
            == []
        )
    rows = _rows()
    assert [(r["kind"], r["entry_id"], r["detail"]["minutes"]) for r in rows] == [
        (ledger_pay.LC_CREDIT, "s-m3", 3),
        (ledger_pay.LC_CREDIT, "s-m5", 2),
    ]
    assert all(earned_time.verified(r, KEY) for r in rows)
    assert credit.session_minutes("s") == {1, 2, 3, 4, 5}


def test_a_gated_receipt_is_recorded_but_not_tutor_minutes_today() -> None:
    credit.credit_span(unit(10), 10, "tutor", now=NOON)
    receipt = credit.credit_span(unit(7), 7, "lc", now=NOON, **LESSON)
    assert receipt.recorded, receipt.error
    assert (receipt.minutes, receipt.minutes_today) == (7, 10)
    assert unit_credit.ledger_minutes_today(NOON) == 10
    assert (
        unit_credit.ledger_minutes_today(NOON, frozenset({ledger_pay.LC_CREDIT})) == 7
    )


def test_the_daily_cap_is_per_kind() -> None:
    cap = ledger_pay.DAILY_CAP_MINUTES
    assert credit.credit_span(unit(cap), cap, "lc", now=NOON, **LESSON).minutes == cap
    tutor = credit.credit_span(unit(20), 20, "tutor", now=NOON)
    assert (tutor.recorded, tutor.minutes) == (True, 20)
    more = credit.credit_span(unit(5), 5, "lc2", now=NOON, **LESSON)
    assert more.error == credit.DAILY_CAP_ERROR


def test_the_earner_and_the_stats_ignore_gated_minutes() -> None:
    where = default_paths()
    credit.credit_span(unit(100), 100, "lc", now=NOON, **LESSON)
    units = earned_time.credit_units(
        earned_time.TUTOR, where.ledger, where.key_file, DAY
    )
    assert units == 0  # read fine, nothing of it the tutor's
    credit.credit_span(unit(10), 10, "tutor", now=NOON)
    tutor_only = earned_time.credit_units(
        earned_time.TUTOR, where.ledger, where.key_file, DAY
    )
    assert tutor_only == 10  # one unit a minute before the weekday quota
    assert progress.ledger_minutes_by_day() == {DAY.isoformat(): 10}


def test_the_carry_bank_ignores_gated_minutes() -> None:
    sat = datetime(2026, 10, 24, 12, tzinfo=ZONE).timestamp()  # quota 50
    credit.credit_span(BlockReady(120, 7200.0, sat, 0, 0), 120, "lc", now=sat, **LESSON)
    sunday = carry.bank_now(sat + 86_400)
    assert (sunday.before, sunday.target) == (0, 0)
    assert carry.spend(now=sat + 86_400) == sunday
    assert {r["kind"] for r in _rows()} == {ledger_pay.LC_CREDIT}


def test_a_gated_lesson_pays_once_through_upkeep_and_a_restart(tmp_path: Path) -> None:
    engine = _teach(tmp_path)
    rows = _rows()
    assert rows
    assert {r["kind"] for r in rows} == {ledger_pay.LC_CREDIT}
    assert {(r["detail"]["subject"], r["detail"]["module"]) for r in rows} == {
        (LC, "a")
    }
    engine.backfill_today()
    engine.backfill_today()
    again = Engine(store=Store(tmp_path), now=ManualClock(T0 / 1000 + 900))
    again.backfill_today()
    assert _rows() == rows


def test_backfill_tags_a_non_live_gated_session_with_its_own_card(
    tmp_path: Path,
) -> None:
    first = _teach(tmp_path, credit_fn=FakeCredit(error="down"))
    assert not default_paths().ledger.exists()
    later = Engine(store=Store(tmp_path), now=ManualClock(T0 / 1000 + 900))
    later.backfill_today()
    later.backfill_today()
    rows = _rows()
    assert rows
    assert {r["detail"]["session_id"] for r in rows} == {first.session_id}
    assert {r["kind"] for r in rows} == {ledger_pay.LC_CREDIT}
    assert {(r["detail"]["subject"], r["detail"]["module"]) for r in rows} == {
        (LC, "a")
    }
