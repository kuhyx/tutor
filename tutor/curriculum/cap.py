# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The daily new-card cap: its value, the day's lift and its refusal.

``DOCS-contract-curriculum.md`` §6. The cap is the latest valid ``new_cap``
event's ``n`` (Settings, any device), else :data:`NEW_CAP`. A ``cap_lift``
event for a PC-local day switches the cap off for that whole day on every
device ("Learn more anyway": ``session_start`` with ``lift_cap``).
``new_today`` (``rules``) keeps counting honestly either way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tutor.credit import local_day
from tutor.curriculum.errors import DAILY_NEW_CAP, RequestError
from tutor.curriculum.eventlog import cap_lift_event
from tutor.curriculum.no_card import due_in_subject

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.fold import Fold
    from tutor.curriculum.records import Module
    from tutor.curriculum.rules import View

NEW_CAP: Final = 25  # with no ``new_cap`` event
LIFT_CAP: Final = "lift_cap"  # the ``next`` step of a ``daily_new_cap``


def day_of(now_ms: int) -> str:
    """The PC-local ISO date of ``now_ms``."""
    return local_day(now_ms / 1000)[0]


def effective_cap(fold: Fold) -> int:
    """The latest ``new_cap`` (``eventlog.parse`` kept 1..200 only), else 25."""
    return fold.new_cap or NEW_CAP


def lifted_today(fold: Fold, now_ms: int) -> bool:
    """Whether a ``cap_lift`` names today's PC-local date."""
    return day_of(now_ms) in fold.lifted_days


def new_today(fold: Fold, now_ms: int) -> int:
    """Cards newly taught on today's PC-local date, all subjects."""
    today = day_of(now_ms)
    return sum(
        day_of(at) == today for state in fold.cards.values() for at in state.new_at
    )


def check(view: View, fold: Fold, chosen: tuple[str, Module], now_ms: int) -> None:
    """Raise ``daily_new_cap`` if teaching ``chosen`` (card, module) passes the cap.

    A taught card (re-teaching) is free; so is anything on a lifted day.
    """
    card, module = chosen
    if fold.card(view.subject, card).taught or lifted_today(fold, now_ms):
        return
    new, limit = new_today(fold, now_ms), effective_cap(fold)
    if new >= limit:
        due = due_in_subject(view, fold, now_ms)
        raise cap_error(view.title, module=module, new=new, cap=limit, due=due)


def lift(ctx: Context) -> bool:
    """Lift today's cap (a worker ``cap_lift``); False when it already was."""
    now = ctx.clock()
    if lifted_today(ctx.fold(), now):
        return False
    ctx.log.append([cap_lift_event(day_of(now), dev=ctx.device, at=now)])
    return True


def cap_error(
    title: str, *, module: Module, new: int, cap: int, due: int
) -> RequestError:
    """``daily_new_cap`` with everything a one-tap "Learn more anyway" needs.

    ``module``: where the next new card is; ``due``: the subject's due
    reviews (``rules.due_in_subject``).
    """
    cards = "card" if new == 1 else "cards"
    limit = "the daily limit" if new == cap else f"the daily limit is {cap}"
    msg = f"You learned {new} new {cards} today ({limit}). “{module.title}” is open."
    extra: dict[str, object] = {
        "subject_title": title,
        "new_today": new,
        "new_cap": cap,
        "module": module.id,
        "module_title": module.title,
        "due_in_subject": due,
        "next": LIFT_CAP,
    }
    return RequestError(DAILY_NEW_CAP, msg, extra=extra)
