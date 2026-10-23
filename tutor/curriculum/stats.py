# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``stats`` node (``DOCS-contract-curriculum.md`` §7).

``{"today": {"day","credited_minutes","active_minutes","target","new","new_cap",
"new_cap_lifted","banked","prepaid"},
"days": {day: {"minutes","taught","reviews"}}}``. Minutes are the verified
ledger's (``progress.ledger_minutes_by_day``, the rows the earner pays);
``taught`` counts cards newly taught that day and ``reviews`` the reviews the
fold kept, both on the PC-local date. ``active_minutes`` sums the engaged
time of the sessions started today (the Session header's day total: a new
card is a new session, so its own clock starts at 0). ``banked`` /
``prepaid`` are the carry-over bank's (``DOCS-contract-carry.md``), read only:
the worker spends before it builds this node.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from tutor import carry, history, progress, resume
from tutor.cardflow import TARGET_MINUTES
from tutor.credit import local_day, target_minutes
from tutor.curriculum.cap import effective_cap, lifted_today, new_today

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context


def _day(ms: int) -> str:
    return local_day(ms / 1000)[0]


def active_minutes(sessions_dir: Path, day: str) -> int:
    """Whole minutes of engaged time in the sessions started on ``day``."""
    seconds = 0.0
    for path in sessions_dir.glob(f"{day.replace('-', '')}-*.jsonl"):
        state = resume.replay(path) if history.SESSION_ID.fullmatch(path.stem) else None
        seconds += state.conversation.clock.active_seconds if state else 0.0
    return int(seconds // 60)


def stats(ctx: Context, minutes: dict[str, int] | None = None) -> dict[str, Any]:
    """The stats node; ``minutes`` (day -> minutes) defaults to the ledger's."""
    per_day = progress.ledger_minutes_by_day() if minutes is None else minutes
    folded = ctx.fold()
    now = ctx.clock()
    taught = Counter(_day(at) for s in folded.cards.values() for at in s.new_at)
    reviews = Counter(_day(e["at"]) for e in folded.kept if e["k"] == "review")
    today = _day(now)
    bank = carry.bank_now(now / 1000)
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
            "active_minutes": active_minutes(ctx.data_dir / "sessions", today),
            "target": target_minutes(now / 1000),
            "new": new_today(folded, now),
            "new_cap": effective_cap(folded),
            "new_cap_lifted": lifted_today(folded, now),
            "banked": bank.banked,
            "prepaid": bank.prepaid,
        },
        "days": days,
    }
