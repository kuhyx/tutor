# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The LeetCode bar's session map: LeetCode accounting for a theory lesson.

DISPLAY ONLY (``DOCS-contract-leetcode-bar.md``). Nothing that pays, caps or
refuses a turn may read this module: the numbers are leetcode-guard's word,
fetched from its loopback route (``guard_route``), and a lesson is credited
the same whether the route answers or not.

A session is a LeetCode theory session when the guard's signed phase is
``theory`` and the session's card belongs to a ``(subject, module)`` pair in
its ``teachable`` list (``theory_phase``, which fails closed). Its map says
which unit and how far through the module the learner is (from the tutor's
own cards), whether today is full, and the guard's minutes-to-credit. A
number the guard could not give (route down, slow, not 200, bad JSON, null,
another day or unit, or any value that is not a plausible count) is left OUT,
never 0 and never coerced: the app paints ``?`` for it. Whatever the guard
sends, nothing raises out of :func:`session_map`.
"""

from __future__ import annotations

import http.client
import logging
import time
from typing import TYPE_CHECKING, Any, Final

from tutor import credit, guard_route, ledger_pay, unit_credit
from tutor.curriculum import theory_phase

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec

REFRESH_S: Final = 60.0  # the worker's tick re-asks at most this often
MAX_COUNT: Final = 10_000  # no real minute or credit count is larger
_logger = logging.getLogger(__name__)


def _count(value: object, low: int = 0) -> int | None:
    """``value`` when it is an int (no bool, float or string) in ``low..MAX_COUNT``."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if low <= value <= MAX_COUNT else None


def _numbers(unit: str, at: float) -> dict[str, int]:
    """The guard's minutes-to-credit for ``unit`` today; ``{}`` when unknown."""
    got = guard_route.fetch()
    if got is None or got.get("checked") is not True or got.get("phase") != "theory":
        return {}
    if got.get("day") != credit.local_day(at)[0]:
        return {}  # yesterday's answer
    theirs = got.get("unit")
    if theirs is not None and theirs != unit:
        return {}  # another unit's minutes (or not a unit name at all)
    per = _count(got.get("minutes_per_credit"), 1)
    into = _count(got.get("minutes_into_credit"))
    if into is not None and per is not None and into > per:
        into = None  # a credit is earned at per_credit: more is not a reading
    found = {
        "into": into,
        "per_credit": per,
        "credits": _count(got.get("credits_today")),
        "needed": _count(got.get("needed")),
    }
    return {key: n for key, n in found.items() if n is not None}


def _guard_numbers(unit: str, at: float) -> dict[str, int]:
    """:func:`_numbers`, fenced: the guard's word never raises into a publish."""
    try:
        return _numbers(unit, at)
    except OSError, ValueError, TypeError, RecursionError, http.client.HTTPException:
        _logger.warning("guard theory answer unreadable, bar blank", exc_info=True)
        return {}


def _counts(
    ctx: Context, subject: str, module: str, cards: dict[str, CardRec]
) -> tuple[int, int]:
    """(taught, total) of the module's live cards, from the tutor's own data."""
    live = [
        cid for cid, rec in cards.items() if rec.module == module and not rec.suspended
    ]
    done = ctx.fold().taught_ids(subject)
    return sum(cid in done for cid in live), len(live)


def session_map(
    ctx: Context, subject: str, card_id: str, at: float
) -> dict[str, Any] | None:
    """The session map for ``card_id`` of ``subject`` at ``at``; ``None``: no bar.

    ``None`` for any session that is not a LeetCode theory session (the app
    then paints today's bar unchanged) and, without a network call, whenever
    the guard's phase is missing, unverifiable or does not list the card.
    """
    if subject not in theory_phase.GATED:
        return None
    grant = theory_phase.current()
    cards = ctx.subjects.cards(subject)
    rec = cards.get(card_id)
    if grant is None or rec is None or (subject, rec.module) not in grant.pairs:
        return None
    taught, total = _counts(ctx, subject, rec.module, cards)
    full = unit_credit.ledger_minutes_today(at) >= ledger_pay.DAILY_CAP_MINUTES
    local = {"unit": grant.unit, "taught": taught, "total": total, "full": full}
    return local | _guard_numbers(grant.unit, at)


class Published:
    """What the relay last published per session, and when the guard was asked."""

    def __init__(self, mono: Callable[[], float] = time.monotonic) -> None:
        """Nothing published yet; ``mono`` is the clock the 60 s rule reads."""
        self.mono = mono
        self.maps: dict[str, dict[str, Any]] = {}
        self.running: set[str] = set()  # published sessions that were not stopped
        self.asked = float("-inf")

    def note(self, sid: str, lc_map: dict[str, Any] | None) -> None:
        """Remember ``sid``'s published map; a map means the guard was just asked."""
        if lc_map is None:
            self.maps.pop(sid, None)
            return
        self.maps[sid] = lc_map
        self.asked = self.mono()

    def running_is(self, sid: str, *, running: bool) -> None:
        """Remember whether ``sid`` was published as running (not stopped)."""
        (self.running.add if running else self.running.discard)(sid)

    def due(self) -> bool:
        """Whether the tick may ask the guard again (once per :data:`REFRESH_S`)."""
        return self.mono() - self.asked >= REFRESH_S

    def changed(self, sid: str, lc_map: dict[str, Any] | None) -> bool:
        """Whether ``lc_map`` differs from what ``sid`` shows now."""
        return lc_map != self.maps.get(sid)

    def stale(self, live: str) -> list[str]:
        """Sessions still showing a map that are not ``live`` (history carries none)."""
        return [sid for sid in self.maps if sid != live]
