# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Anki reviews done while Claude was unavailable, paid as tutor minutes.

AnkiDroid syncs to anki-guard's ``anki --syncserver``; its copy of the
collection is the source. A counted review (any deck) whose time -- its
revlog id, unix ms -- falls in an :mod:`tutor.unavailable` window is eligible.

**Pay.** One credited minute per 60 s of a local day's summed eligible time,
as ``credit`` rows of session ``anki-<YYYY-MM-DD>`` (the tutor earner, so
earned_time needs nothing new). Minute ``n`` "ended" at the review that took
the running total past ``n`` minutes, so a row never spans local midnight.
Days are local calendar days, not anki-guard's rollover-hour Anki days: the
ledger's day is the row's ``ended_at`` date. Re-crediting is idempotent:
:func:`tutor.unit_credit.credit_units` skips the minutes the ledger already
pays, so every pass recomputes the cumulative total and writes only the new.

Reading the collection (a snapshot copy, never the open file) is
:mod:`tutor.anki_collection`; the watcher is :mod:`tutor.anki_watch`.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Final

from tutor import credit, unavailable, unit_credit
from tutor.anki_collection import (
    AnkiError,
    collection_path,
    last_sync_at,
    reviews,
    snapshot,
)
from tutor.clock import BlockReady

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

MINUTE_MS: Final = 60_000
_DAYS_BACK: Final = 1  # a review at 23:50 synced at 00:10 still pays yesterday
# One pass at a time (watcher and anki_status): two passes reading different
# totals would write overlapping spans under different ids.
_PASS: Final = threading.Lock()
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pass:
    """One credit pass: today's eligible minutes and the ledger rows written."""

    day: str
    eligible_min: int
    rows: list[dict[str, Any]]


def units(
    found: Iterable[tuple[int, int]], windows: list[unavailable.Window]
) -> list[BlockReady]:
    """One unit per full eligible minute of ``found`` (one day's reviews)."""
    total_ms = 0
    out: list[BlockReady] = []
    for review_id, spent in found:
        at = review_id / 1000
        if not unavailable.unavailable_at(at, windows):
            continue
        total_ms += max(int(spent), 0)
        while total_ms >= (len(out) + 1) * MINUTE_MS:
            out.append(BlockReady(len(out) + 1, total_ms / 1000, at, 0, 0))
    return out


def session_for(day: str) -> str:
    """The ledger session id Anki minutes of local ``day`` are paid under."""
    return f"anki-{day}"


def _by_day(found: list[tuple[int, int]]) -> dict[str, list[tuple[int, int]]]:
    days: dict[str, list[tuple[int, int]]] = {}
    for review in found:
        days.setdefault(credit.local_day(review[0] / 1000)[0], []).append(review)
    return days


def credit_pass(now: float, source: Path | None = None) -> Pass:
    """Pay every new eligible minute of today and yesterday; today's figures.

    Raises:
        AnkiError: The collection is missing or unreadable.
    """
    today, start, _ = credit.local_day(now)
    since = start
    for _ in range(_DAYS_BACK):
        since = credit.local_day(since - 1)[1]
    windows = unavailable.windows()
    with _PASS:
        with snapshot(source or collection_path()) as copy:
            found = reviews(copy, since)
        eligible, written = 0, []
        for day, day_reviews in sorted(_by_day(found).items()):
            day_units = units(day_reviews, windows)
            eligible = len(day_units) if day == today else eligible
            written += unit_credit.credit_units(day_units, session_for(day), now=now)
    for row in written:
        _logger.warning(
            "anki: %s paid %d min (%s)",
            row["entry_id"],
            row["minutes"],
            "ok" if row["recorded"] else row["error"],
        )
    return Pass(today, eligible, written)


def credit_now(now: float | None = None, source: Path | None = None) -> Pass | None:
    """:func:`credit_pass`, with a missing or unreadable collection logged."""
    try:
        return credit_pass(time.time() if now is None else now, source)
    except AnkiError as exc:
        _logger.warning("anki credit skipped: %s", exc)
        return None


def status(now: float, source: Path | None = None) -> dict[str, Any]:
    """The ``anki_status`` result, after a credit pass (a missing collection: 0).

    Raises:
        AnkiError: The collection exists but cannot be read.
    """
    path = source or collection_path()
    day = credit.local_day(now)[0]
    eligible = credit_pass(now, path).eligible_min if path.exists() else 0
    window = unavailable.current(now)
    return {
        "credited_today_min": len(credit.session_minutes(session_for(day))),
        "eligible_today_min": eligible,
        "last_sync_at": last_sync_at(path),
        "unavailable": (
            None if window is None else {"until": window.end, "reason": window.reason}
        ),
    }
