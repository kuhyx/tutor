# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Today's tutor progress as the evening gate reads it."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import earned_time

from tutor import gate_state
from tutor.tests import _gate_support as sup

if TYPE_CHECKING:
    import pytest


def test_no_ledger_is_zero_minutes_unpaid() -> None:
    got = gate_state.read_progress(sup.paths(), sup.TUESDAY)
    assert got == gate_state.Progress(minutes=0, quota=15, paid=False)


def test_partial_minutes_show_against_the_weekday_quota() -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 7, 7)])
    got = gate_state.read_progress(sup.paths(), sup.TUESDAY)
    assert got == gate_state.Progress(minutes=7, quota=15, paid=False)


def test_the_full_quota_is_paid() -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 15, 15)])
    got = gate_state.read_progress(sup.paths(), sup.TUESDAY)
    assert got == gate_state.Progress(minutes=15, quota=15, paid=True)


def test_quota_follows_the_day_of_the_week() -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.FRIDAY, 15, 15)])
    friday = gate_state.read_progress(sup.paths(), sup.FRIDAY)
    assert friday == gate_state.Progress(minutes=15, quota=30, paid=False)
    sup.put(sup.paths().ledger, [sup.row(sup.SATURDAY, 50, 50)])
    saturday = gate_state.read_progress(sup.paths(), sup.SATURDAY)
    assert saturday == gate_state.Progress(minutes=50, quota=50, paid=True)


def test_yesterdays_credit_does_not_count() -> None:
    sup.put(sup.paths().ledger, [sup.row(date(2026, 11, 16), 15, 15)])
    got = gate_state.read_progress(sup.paths(), sup.TUESDAY)
    assert got is not None
    assert (got.minutes, got.paid) == (0, False)


def test_a_forged_row_counts_for_nothing() -> None:
    forged = sup.row(sup.TUESDAY, 15, 15)
    forged["hmac"] = "0" * 64
    sup.put(sup.paths().ledger, [forged])
    got = gate_state.read_progress(sup.paths(), sup.TUESDAY)
    assert got is not None
    assert got.paid is False


def test_an_unreadable_key_is_could_not_check() -> None:
    sup.paths().key_file.unlink()
    assert gate_state.read_progress(sup.paths(), sup.TUESDAY) is None


def test_a_broken_ledger_is_could_not_check() -> None:
    ledger = sup.paths().ledger
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{not json", encoding="utf-8")
    assert gate_state.read_progress(sup.paths(), sup.TUESDAY) is None


def test_before_the_quota_era_minutes_are_units() -> None:
    old = date(2026, 10, 10)
    sup.put(sup.paths().ledger, [sup.row(old, 20, 20)])
    got = gate_state.read_progress(sup.paths(), old)
    assert got == gate_state.Progress(minutes=20, quota=60, paid=False)


def test_an_earner_that_raises_is_could_not_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_a: object, **_k: object) -> int:
        raise ValueError

    monkeypatch.setattr(earned_time, "credit_units", boom)
    assert gate_state.read_progress(sup.paths(), sup.TUESDAY) is None


def test_local_today_is_a_date() -> None:
    assert isinstance(gate_state.local_today(), date)
