# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``stats`` node (``DOCS-contract-curriculum.md`` §7).

``{"today": {"day","credited_minutes","target","new","new_cap"},
"days": {day: {"minutes","taught","reviews"}}}``. Minutes are the verified
ledger's (``progress.ledger_minutes_by_day``, the rows the earner pays);
``taught`` counts cards newly taught that day and ``reviews`` the reviews the
fold kept, both on the PC-local date.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from tutor import progress
from tutor.cardflow import TARGET_MINUTES
from tutor.credit import local_day
from tutor.curriculum.rules import NEW_CAP, new_today

if TYPE_CHECKING:
    from tutor.curriculum.context import Context


def _day(ms: int) -> str:
    return local_day(ms / 1000)[0]


def stats(ctx: Context, minutes: dict[str, int] | None = None) -> dict[str, Any]:
    """The stats node; ``minutes`` (day -> minutes) defaults to the ledger's."""
    per_day = progress.ledger_minutes_by_day() if minutes is None else minutes
    folded = ctx.fold()
    now = ctx.clock()
    taught = Counter(_day(at) for s in folded.cards.values() for at in s.new_at)
    reviews = Counter(_day(e["at"]) for e in folded.kept if e["k"] == "review")
    today = _day(now)
    days = {
        day: {
            "minutes": per_day.get(day, 0),
            "taught": taught[day],
            "reviews": reviews[day],
        }
        for day in sorted({*per_day, *taught, *reviews})
    }
    return {
        "today": {
            "day": today,
            "credited_minutes": min(per_day.get(today, 0), TARGET_MINUTES),
            "target": TARGET_MINUTES,
            "new": new_today(folded, now),
            "new_cap": NEW_CAP,
        },
        "days": days,
    }
