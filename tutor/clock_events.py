# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What the engagement clock (:mod:`tutor.clock`) reads and emits, as values.

Event times (when a reply or an answer counts as given) and the unit it
releases (:class:`BlockReady`). :mod:`tutor.clock` re-exports every name, so
callers keep importing them from there. Pure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# How far back the page's first Send press may date a reply (its retry window).
SEND_GRACE: Final = 300.0
# How old an answer may be and still back focus time (relay ``MAX_EVENT_AGE_MS``).
ACTIVITY_MAX_AGE: Final = 48 * 3600.0


def reply_time(received: float, sent_at: float | None) -> float:
    """When a reply was sent: the page's first Send press if within grace."""
    if sent_at is not None and 0.0 <= received - sent_at <= SEND_GRACE:
        return sent_at
    return received


def activity_time(received: float, sent_at: float | None) -> float:
    """When an answer was given, for the focus beat it backs.

    ``sent_at`` if it lies in ``[received - ACTIVITY_MAX_AGE, received]``, else
    ``received``: an offline answer backs the time it was given, not the sync
    time, and a clock ahead of the server never puts a beat in the future.
    Not :func:`reply_time`, whose short grace guards the credit arithmetic.
    """
    if sent_at is not None and 0.0 <= received - sent_at <= ACTIVITY_MAX_AGE:
        return sent_at
    return received


@dataclass(frozen=True)
class BlockReady:
    """One newly earned active minute (a "unit"), ready to be credited.

    Attributes:
        block: Which unit of the session, 1..MAX_UNITS (the n-th active minute).
        active_seconds: The session's *cumulative* active seconds at the moment
            the unit was earned (>= block * UNIT_SECONDS - the session's carry_in).
        ended_at: Unix time of the event that earned it.
        checks_passed: Checks passed so far this session.
        checks_total: Checks resolved (passed or failed) so far this session.
    """

    block: int
    active_seconds: float
    ended_at: float
    checks_passed: int
    checks_total: int
