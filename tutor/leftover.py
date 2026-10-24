# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Leftover seconds: a day pays its whole active minutes, not each card's.

Each card is its own session with its own clock, and a clock pays whole
minutes only, so every card used to drop its part minute (kuhy, 2026-10-24:
12 cards of 31.2 active minutes paid 24). Two parts fix it:

* **Seed.** A new card opens with :func:`seed`, the day's active seconds so
  far modulo a minute, as its clock's ``carry_in`` (logged on its ``start``
  event, so replay reproduces it). With every card seeded, the day's units
  telescope to ``floor(day's active / 60)``.
* **Top-up.** Cards that were never seeded (before this, or a day's first
  pre-fix card) still lost their part minutes. :func:`pay` writes, per day,
  ``floor(closed active / 60) - closed units``: a seeded card adds 0 to it,
  an unseeded one 0 or 1, so the cumulative figure only grows. Today's
  newest card can still accrue (its part minute seeds the next card), so it
  is left out; once a day is past, all its cards count.

A top-up row is a signed ``credit`` row, ``entry_id`` ``leftover-<day>-m<n>``
(``n`` = the day's cumulative owed minutes, ``minutes`` the delta over what
the ledger already pays under that day's ids), ``ended_at`` = the write time.
A past day's minutes therefore count today, and what passes today's quota
is banked for later days (:mod:`tutor.carry`). Only the live worker pays.
"""

from __future__ import annotations

from collections import defaultdict
import logging
import re
import threading
import time
from typing import TYPE_CHECKING, Any, Final

import earned_time

from tutor import history, resume
from tutor.clock import MAX_UNITS, UNIT_SECONDS
from tutor.credit import append_locked, local_day
from tutor.ledger_io import LedgerError, default_paths, exclusive, read_key, read_rows
from tutor.ledger_pay import CREDIT, paying
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from tutor.ledger_io import Paths

LEFTOVER_ID: Final = re.compile(r"leftover-(\d{4}-\d{2}-\d{2})-m\d+", re.ASCII)
# One pass at a time in this process; the ledger lock covers other processes.
_PASS: Final = threading.Lock()
_logger = logging.getLogger(__name__)


def _cards(sessions_dir: Path, day_prefix: str) -> list[tuple[float, int]]:
    """``(active seconds, units)`` of the day's cards, oldest first."""
    out = []
    for path in sorted(sessions_dir.glob(f"{day_prefix}-*.jsonl")):
        if not history.SESSION_ID.fullmatch(path.stem):
            continue
        state = resume.replay(path)
        if state is None:
            continue
        clock = state.conversation.clock
        units = int(str(clock.snapshot()["blocks_earned"]))
        out.append((clock.active_seconds, units))
    return out


def seed(sessions_dir: Path, day_prefix: str) -> float:
    """The day's active seconds so far modulo a minute: a new card's ``carry_in``."""
    total = sum(active for active, _ in _cards(sessions_dir, day_prefix))
    return round(total % UNIT_SECONDS, 3)


def owed(sessions_dir: Path, day_prefix: str, *, live: bool) -> int:
    """Minutes the day's cards earned together but not one by one.

    ``live``: the day is today, so its newest card (still accruing) is left out.
    """
    cards = _cards(sessions_dir, day_prefix)
    closed = cards[:-1] if live else cards
    whole = int(sum(active for active, _ in closed) // UNIT_SECONDS)
    paid = sum(min(units, MAX_UNITS) for _, units in closed)
    return max(0, whole - paid)


def _row(day: str, owed_n: int, minutes: int, now: float, key: bytes) -> dict[str, Any]:
    """The signed row paying ``minutes`` more of ``day``'s leftover, dated ``now``."""
    row: dict[str, Any] = {
        "kind": CREDIT,
        "entry_id": f"leftover-{day}-m{owed_n}",
        "day": local_day(now)[0],
        "created_at": float(now),
        "detail": {
            "session_id": f"leftover-{day}",
            "block": owed_n,
            "minutes": minutes,
            "ended_at": float(now),
        },
    }
    row["hmac"] = str(earned_time.entry_signature(row, key))
    return row


def _paid(rows: list[object], key: bytes) -> dict[str, int]:
    """Day -> leftover minutes the ledger already pays for it."""
    out: dict[str, int] = defaultdict(int)
    for entry, (_, minutes) in paying(rows, key).items():
        if found := LEFTOVER_ID.fullmatch(entry):
            out[found[1]] += minutes
    return out


def _iso(prefix: str) -> str:
    return f"{prefix[:4]}-{prefix[4:6]}-{prefix[6:]}"


def pay(
    sessions_dir: Path | None = None,
    *,
    now: float | None = None,
    days: Iterable[str] | None = None,
    paths: Paths | None = None,
) -> int:
    """Pay every day's owed leftover; the minutes written (0 on failure).

    ``days``: ``YYYYMMDD`` prefixes (default: every day with a transcript, so
    the past is paid back once). Writes nothing when the ledger is current, so
    a pass every minute fires no ledger watcher. A failure is logged, never
    raised.
    """
    folder = sessions_dir or data_dir() / "sessions"
    where = paths or default_paths()
    moment = time.time() if now is None else now
    today = local_day(moment)[0].replace("-", "")
    if days is None:
        days = sorted({p.name[:8] for p in folder.glob("*.jsonl")})
    owed_by = {d: owed(folder, d, live=d == today) for d in sorted(days) if d <= today}
    key = read_key(where.key_file)
    if key is None or not any(owed_by.values()):
        return 0
    try:
        with _PASS, exclusive(where.lock):
            paid = _paid(read_rows(where.ledger), key)
            fresh = [
                _row(_iso(d), n, n - paid.get(_iso(d), 0), moment, key)
                for d, n in owed_by.items()
                if n > paid.get(_iso(d), 0)
            ]
            return sum(_append(row, where, key) for row in fresh)
    except (LedgerError, OSError) as exc:
        _logger.warning("leftover not paid: %s", exc)
        return 0


def _append(row: dict[str, Any], where: Paths, key: bytes) -> int:
    """Append one leftover row (the writer may trim it); the minutes it paid."""
    refusal, minutes = append_locked(row, where.ledger, key)
    _logger.info(
        "leftover: %s paid %d min (%s)", row["entry_id"], minutes, refusal or "ok"
    )
    return minutes
