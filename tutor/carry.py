# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The carry-over bank: minutes past a day's quota pay later days.

Contract: ``DOCS-contract-carry.md``. The balance is never stored; it is
derived from the verified ledger on every call, like leetcode-guard's
credit bank. From :data:`CARRY_FROM`, day by day:
``balance = clamp(balance - spent_d + max(0, paid_d - quota_d), 0, BANK_CAP)``,
where ``paid_d`` counts every verified tutor minute ending on ``d`` (carry rows
included) and ``spent_d`` the carry rows of ``d`` the ledger holds. A day the
worker never spent on keeps its balance.

Today's carry is ``min(balance before today, quota today)``. :func:`spend`
tops the ledger up to it with one signed ``credit`` row, ``entry_id``
``carry-<day>-m<n>`` (``n`` = the day's cumulative carry target): a rerun
writes nothing and a later, larger target (yesterday's late phone reviews)
writes only the delta. Only the live worker calls :func:`spend`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
import re
import threading
import time
from typing import TYPE_CHECKING, Any, Final

import earned_time

from tutor.credit import DAILY_TARGET_MINUTES, append_locked, local_day
from tutor.ledger_io import (
    LedgerError,
    default_paths,
    exclusive,
    read_key,
    read_rows,
)
from tutor.ledger_pay import BANK_CAP, CREDIT, DAILY_CAP_MINUTES, paying

if TYPE_CHECKING:
    from tutor.ledger_io import Paths

__all__ = ["BANK_CAP", "CARRY_FROM", "Bank", "bank_now", "bank_of", "spend"]

# The first day whose extra minutes are banked (kuhy, 2026-10-23).
CARRY_FROM: Final = date(2026, 10, 23)
CARRY_ID: Final = re.compile(r"carry-\d{4}-\d{2}-\d{2}-m\d+", re.ASCII)
# One pass at a time in this process; the ledger lock covers other processes.
_PASS: Final = threading.Lock()
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Bank:
    """The bank on one local day, as the ledger shows it.

    ``before``: balance at the day's start; ``target``: carry minutes the day
    should get; ``prepaid``: carry minutes the ledger pays that day;
    ``banked``: balance after the day so far (its spend and its deposit).
    """

    day: str
    before: int
    target: int
    prepaid: int
    banked: int


def quota_for(day: date) -> int:
    """earned_time's tutor quota for ``day`` (60 before the quota existed)."""
    return earned_time.tutor_quota_for(day) or DAILY_TARGET_MINUTES


def _per_day(paid_rows: dict[str, tuple[float, int]]) -> tuple[dict[str, int], ...]:
    """Local day -> verified minutes (all rows), and -> carry minutes."""
    totals: dict[str, int] = {}
    spent: dict[str, int] = {}
    for entry, (ended, minutes) in paid_rows.items():
        day = local_day(ended)[0]
        totals[day] = totals.get(day, 0) + minutes
        if CARRY_ID.fullmatch(entry):
            spent[day] = spent.get(day, 0) + minutes
    return totals, spent


def _after(balance: int, paid: int, spent: int, day: date) -> int:
    """The balance after a day that paid ``paid`` minutes, ``spent`` of them carry."""
    deposit = max(0, min(paid, DAILY_CAP_MINUTES) - quota_for(day))
    return max(0, min(BANK_CAP, balance - spent + deposit))


def bank_of(paid_rows: dict[str, tuple[float, int]], today: date) -> Bank:
    """The bank on ``today`` from the ledger's paying rows (pure)."""
    if today < CARRY_FROM:
        return Bank(today.isoformat(), 0, 0, 0, 0)
    totals, spent = _per_day(paid_rows)
    balance, day = 0, CARRY_FROM
    while day < today:
        iso = day.isoformat()
        balance = _after(balance, totals.get(iso, 0), spent.get(iso, 0), day)
        day += timedelta(days=1)
    iso = today.isoformat()
    prepaid = spent.get(iso, 0)
    after = _after(balance, totals.get(iso, 0), prepaid, today)
    return Bank(iso, balance, min(balance, quota_for(today)), prepaid, after)


def _today(moment: float) -> date:
    return date.fromisoformat(local_day(moment)[0])


def bank_now(moment: float, *, paths: Paths | None = None) -> Bank:
    """The bank on ``moment``'s local day; empty when the ledger is unreadable."""
    where = paths or default_paths()
    key = read_key(where.key_file)
    today = _today(moment)
    try:
        rows = read_rows(where.ledger) if key else []
    except LedgerError as exc:
        _logger.warning("ledger unreadable, carry-over unknown: %s", exc)
        rows = []
    return bank_of(paying(rows, key) if key else {}, today)


def carry_row(bank: Bank, key: bytes, *, now: float) -> dict[str, Any]:
    """The signed row topping ``bank.day``'s carry up to ``bank.target``."""
    row: dict[str, Any] = {
        "kind": CREDIT,
        "entry_id": f"carry-{bank.day}-m{bank.target}",
        "day": bank.day,
        "created_at": float(now),
        "detail": {
            "session_id": f"carry-{bank.day}",
            "block": bank.target,
            "minutes": bank.target - bank.prepaid,
            "ended_at": float(now),
            "carry": True,
        },
    }
    row["hmac"] = str(earned_time.entry_signature(row, key))
    return row


def spend(*, paths: Paths | None = None, now: float | None = None) -> Bank | None:
    """Top today's carry up to its target; the bank after, ``None`` on failure.

    Writes nothing when the ledger already pays the target, so a pass every
    minute fires no ledger watcher. A failure is logged, never raised.
    """
    where = paths or default_paths()
    moment = time.time() if now is None else now
    key = read_key(where.key_file)
    if key is None:
        return None
    today = _today(moment)
    try:
        with _PASS, exclusive(where.lock):
            bank = bank_of(paying(read_rows(where.ledger), key), today)
            if bank.target <= bank.prepaid:
                return bank
            row = carry_row(bank, key, now=moment)
            refusal, paid = append_locked(row, where.ledger, key)
            bank = bank_of(paying(read_rows(where.ledger), key), today)
    except (LedgerError, OSError) as exc:
        _logger.warning("carry-over not spent: %s", exc)
        return None
    _logger.info(
        "carry-over: %s paid %d min (%s); banked %d",
        row["entry_id"],
        paid,
        refusal or "ok",
        bank.banked,
    )
    return bank
