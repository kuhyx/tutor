# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""App reviews (the phone's or desktop's offline Review) paid as tutor minutes.

The app records each rating as a ``review`` event (``log/{dev}/{eid}``,
``dur_ms`` = shown -> rated); the worker mirrors them into ``log.jsonl``.
This pays them on the tutor rung, under the tutor's own daily cap (the
ledger's: every verified credit row of the day counts against it).

**What earns.** Per review: ``min(dur_ms, 60 s)``; a review under
:data:`MIN_REVIEW_SECONDS` (the drill's quick-pick rule) or without a
duration earns nothing, nor does a review a ``review_undo`` names (the
Review's Back; a minute already paid before the undo synced stays paid,
since rows are never taken back). One credited minute per 60 s of a (local day,
device)'s summed time, in ``at`` order. Minute ``n`` "ended" at the review
that took the running total past ``n`` minutes -- anchored to the review,
never to when it synced -- so a row never spans local midnight.

**Never paid twice.** Session ``review-<YYYYMMDD>-<dev>`` per local day and
device; :func:`tutor.unit_credit.credit_units` skips minutes the ledger
already pays, so every pass recomputes the totals and writes only the new
minutes. The PC drill writes its reviews under the worker's own device id
and credits them itself (``drill.py``), so the worker's own reviews are
skipped; with no own id known nothing is paid (fail closed). AnkiDroid
minutes (``anki.py``) come from the Anki collection, never from this log.
Only today and yesterday are paid (a review at 23:59 synced at 00:05 still
pays its own day; older reviews, or ones dated after today, never do).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Final

from tutor import credit, unit_credit
from tutor.clock import UNIT_SECONDS, BlockReady
from tutor.curriculum.fold import undone_eids

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tutor.curriculum.context import Context
    from tutor.curriculum.eventlog import EventLog

MIN_REVIEW_SECONDS: Final = 3.0  # as drill.MIN_PICK_SECONDS: a faster one is a guess
MAX_REVIEW_SECONDS: Final = 60.0  # one review never earns more than a minute
_DAYS_BACK: Final = 1
# One pass at a time: two passes reading different totals could race a span.
_PASS: Final = threading.Lock()
_logger = logging.getLogger(__name__)


def active_seconds(event: dict[str, Any]) -> float:
    """What one review earns: its duration, capped; 0 when quick or unknown."""
    dur = event.get("dur_ms")
    if isinstance(dur, bool) or not isinstance(dur, int):
        return 0.0
    seconds = dur / 1000
    return 0.0 if seconds < MIN_REVIEW_SECONDS else min(seconds, MAX_REVIEW_SECONDS)


def session_for(day: str, dev: str) -> str:
    """The ledger session app reviews of ``dev`` on local ISO ``day`` pay under."""
    return f"review-{day.replace('-', '')}-{dev}"


def _units(reviews: list[dict[str, Any]]) -> list[BlockReady]:
    """One unit per full minute of one session's reviews, in ``at`` order."""
    total, out = 0.0, list[BlockReady]()
    for event in sorted(reviews, key=lambda e: (e["at"], e["eid"])):
        total += active_seconds(event)
        while total >= (len(out) + 1) * UNIT_SECONDS:
            out.append(BlockReady(len(out) + 1, total, event["at"] / 1000, 0, 0))
    return out


def units_by_session(
    events: Iterable[dict[str, Any]], own_dev: str, now: float
) -> dict[str, list[BlockReady]]:
    """Session id -> units, for app reviews of today and yesterday (pure).

    ``own_dev`` is the worker's device id (its drill reviews are skipped);
    empty means none can be told apart, so nothing is returned.
    """
    if not own_dev:
        return {}
    _, start, end = credit.local_day(now)
    since = start
    for _ in range(_DAYS_BACK):
        since = credit.local_day(since - 1)[1]
    events = list(events)
    undone = undone_eids(events)
    sessions: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("k") != "review" or event.get("dev") == own_dev:
            continue
        if event["eid"] in undone:  # taken back with the Review's Back
            continue
        moment = event["at"] / 1000
        if not since <= moment < end:
            continue
        day = credit.local_day(moment)[0]
        sessions.setdefault(session_for(day, str(event["dev"])), []).append(event)
    found = {sid: _units(reviews) for sid, reviews in sorted(sessions.items())}
    return {sid: units for sid, units in found.items() if units}


def credit_pass(log: EventLog, own_dev: str, now: float) -> list[dict[str, Any]]:
    """Pay every new minute of the app reviews in ``log``; the rows written."""
    written: list[dict[str, Any]] = []
    with _PASS:
        for sid, units in units_by_session(log.read(), own_dev, now).items():
            written += unit_credit.credit_units(units, sid, now=now)
    for row in written:
        quiet = row["recorded"] or row["error"] == credit.DAILY_CAP_ERROR
        _logger.log(
            logging.INFO if quiet else logging.WARNING,
            "app review: %s paid %d min (%s)",
            row["entry_id"],
            row["minutes"],
            "ok" if row["recorded"] else row["error"],
        )
    return written


def credit_now(ctx: Context, now: float | None = None) -> list[dict[str, Any]]:
    """:func:`credit_pass` on ``ctx``'s log; a failure is logged, never raised."""
    try:
        return credit_pass(ctx.log, ctx.device, time.time() if now is None else now)
    except (OSError, ValueError) as exc:  # unreadable log line, disk error
        _logger.warning("app review credit skipped: %s", exc)
        return []
