# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The carry-over bank: minutes past a day's quota pay later days.

Quotas used: Fri 2026-10-23 30 (CARRY_FROM), Sat 10-24 / Sun 10-25 50,
Mon 10-26 30, Thu 10-22 15.
"""

from __future__ import annotations

from datetime import date, datetime
import json
import threading
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import earned_time

from tutor import carry, credit, ledger_pay
from tutor.clock import BlockReady
from tutor.ledger_io import default_paths, read_key

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ZONE = ZoneInfo("Europe/Warsaw")


def at(day: int, hour: int = 12, minute: int = 0) -> float:
    """Unix seconds at ``hour:minute`` local on October ``day``, 2026."""
    return datetime(2026, 10, day, hour, minute, tzinfo=ZONE).timestamp()


def own(day: int, minutes: int, *, hour: int = 12, tag: str = "abcd") -> int:
    """Write ``minutes`` own tutor minutes ending on October ``day``; minutes paid."""
    sid = f"202610{day:02d}-{hour:02d}0000-{tag}"
    last = BlockReady(minutes, 60.0 * minutes, at(day, hour), 0, 0)
    receipt = credit.credit_span(last, minutes, sid, now=at(day, hour))
    assert receipt.recorded, receipt.error
    return receipt.minutes


def spent(moment: float) -> carry.Bank:
    """:func:`carry.spend` at ``moment``, which must succeed."""
    bank = carry.spend(now=moment)
    assert bank is not None
    return bank


def rows() -> list[dict[str, Any]]:
    """The ledger's rows as written."""
    raw = json.loads(default_paths().ledger.read_text(encoding="utf-8"))
    found: list[dict[str, Any]] = raw["entries"]
    return found


def carry_rows() -> list[dict[str, Any]]:
    """Only the carry rows, in write order."""
    return [r for r in rows() if str(r["entry_id"]).startswith("carry-")]


def test_the_writer_records_bankable_minutes_past_sixty() -> None:
    assert ledger_pay.DAILY_CAP_MINUTES == 60 + carry.BANK_CAP
    assert own(23, 120) == 120
    assert own(23, 80, tag="beef") == 40  # trimmed at 160


def test_nothing_is_banked_before_carry_from() -> None:
    own(22, 90)  # Thursday, quota 15: 75 extra, but before the bank opened
    bank = carry.bank_now(at(23, 9))
    assert (bank.before, bank.target, bank.prepaid, bank.banked) == (0, 0, 0, 0)
    assert spent(at(23, 9)).prepaid == 0
    assert carry_rows() == []


def test_extra_minutes_deposit_and_are_spent_the_next_day() -> None:
    own(23, 50)  # quota 30: 20 banked
    assert carry.bank_now(at(23, 18)).banked == 20
    bank = spent(at(24, 0, 1))
    assert (bank.before, bank.target, bank.prepaid, bank.banked) == (20, 20, 20, 0)
    (row,) = carry_rows()
    assert row["entry_id"] == "carry-2026-10-24-m20"
    assert row["day"] == "2026-10-24"
    detail = row["detail"]
    assert detail["minutes"] == 20
    assert detail["carry"] is True
    assert detail["session_id"] == "carry-2026-10-24"
    assert credit.local_day(detail["ended_at"])[0] == "2026-10-24"


def test_spend_never_exceeds_the_day_quota() -> None:
    own(23, 110)  # quota 30: 80 banked
    bank = spent(at(24, 8))  # Saturday, quota 50
    assert (bank.before, bank.prepaid, bank.banked) == (80, 50, 30)
    bank = spent(at(26, 8))  # Monday, quota 30; Sunday was skipped
    assert (bank.before, bank.prepaid, bank.banked) == (30, 30, 0)


def test_the_bank_is_capped_at_one_hundred() -> None:
    own(23, 160)  # quota 30: 130 extra, the bank holds 100
    assert carry.bank_now(at(23, 20)).banked == carry.BANK_CAP == 100
    own(24, 100)  # Saturday: 50 carry + 100 own, 100 extra again
    bank = spent(at(24, 13))
    assert (bank.before, bank.prepaid, bank.banked) == (100, 50, 100)


def test_late_minutes_for_yesterday_top_up_with_a_delta_row() -> None:
    own(23, 40)  # 10 banked
    carry.spend(now=at(24, 0, 1))
    own(23, 15, hour=23, tag="late")  # phone reviews of 23:00, synced after midnight
    bank = spent(at(24, 0, 5))
    assert (bank.before, bank.prepaid, bank.banked) == (25, 25, 0)
    ids = [(r["entry_id"], r["detail"]["minutes"]) for r in carry_rows()]
    assert ids == [("carry-2026-10-24-m10", 10), ("carry-2026-10-24-m25", 15)]


def test_a_rerun_writes_nothing() -> None:
    own(23, 45)
    carry.spend(now=at(24, 9))
    before = default_paths().ledger.read_bytes()
    for moment in (at(24, 9), at(24, 10), at(24, 23, 59)):
        assert spent(moment).prepaid == 15
    assert default_paths().ledger.read_bytes() == before


def test_concurrent_passes_spend_once() -> None:
    own(23, 60)  # 30 banked
    threads = [
        threading.Thread(target=carry.spend, kwargs={"now": at(24, 9)})
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [r["entry_id"] for r in carry_rows()] == ["carry-2026-10-24-m30"]


def test_a_day_the_worker_never_spent_keeps_the_balance() -> None:
    own(23, 50)  # 20 banked; no pass runs on Saturday
    bank = spent(at(25, 9))
    assert (bank.before, bank.prepaid, bank.banked) == (20, 20, 0)
    assert [r["entry_id"] for r in carry_rows()] == ["carry-2026-10-25-m20"]


def test_a_full_day_trims_the_carry_and_never_retries_it() -> None:
    own(23, 110)  # 80 banked
    own(24, 150)  # Saturday: 10 minutes of room left under 160
    bank = spent(at(24, 20))
    assert (bank.target, bank.prepaid) == (50, 10)
    before = default_paths().ledger.read_bytes()
    carry.spend(now=at(24, 21))
    assert default_paths().ledger.read_bytes() == before


def test_earned_time_counts_a_carry_row_unchanged() -> None:
    own(23, 40)  # 10 banked
    carry.spend(now=at(24, 9))
    where = default_paths()
    key = read_key(where.key_file)
    assert key is not None
    (row,) = carry_rows()
    assert earned_time.verified(row, key)
    # tutor_match through the consumer's own call. Saturday's quota is 50: 10 minutes pay 10 * 60 // 50 = 12 units, not
    # 0 (refused), 15 (a legacy row) or 60 (the cap).
    units = earned_time.credit_units(
        earned_time.TUTOR, where.ledger, where.key_file, date(2026, 10, 24)
    )
    assert units == 12


def test_an_unreadable_ledger_spends_nothing() -> None:
    where = default_paths()
    where.data_dir.mkdir(parents=True, exist_ok=True)
    where.ledger.write_text("{cut", encoding="utf-8")
    assert carry.spend(now=at(24, 9)) is None
    assert carry.bank_now(at(24, 9)).banked == 0
    assert where.ledger.read_text(encoding="utf-8") == "{cut"


def test_a_day_before_carry_from_has_no_bank() -> None:
    own(22, 90)
    assert carry.bank_now(at(22, 20)) == carry.Bank("2026-10-22", 0, 0, 0, 0)


def test_without_the_key_nothing_is_known_or_spent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    own(23, 50)
    monkeypatch.setenv("TUTOR_KEY", str(tmp_path / "missing.key"))
    assert carry.spend(now=at(24, 9)) is None
    assert carry.bank_now(at(24, 9)).banked == 0
    assert carry_rows() == []
