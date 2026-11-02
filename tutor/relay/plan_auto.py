# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Steps of today's plan the server can see were done: no Done tap needed.

What counts as done, per step ``kind`` (``target`` is the step's argument):

- ``coach``: a coach session on slug ``target`` reached exit (solved or
  revealed) today (``exit_ms`` of ``lc_sessions/``).
- ``sql_lesson``: a lesson of topic ``target`` emitted a mastery summary today
  (``mastered_ms`` of ``sql_lessons/``).
- ``mock``: a mock finished today; with ``target`` ``review`` the step is done
  ``REVIEW_MS`` after that finish. The app opens a result without asking the
  server, so a view is not detectable; ten minutes is the time to read it.
- ``cards``: subject ``target`` has no due review and at least one card of it
  was taught or reviewed today (a subject nobody studied is not "done").

``sql_drill`` and ``note`` steps are only ticked by hand (``plan_step_done``).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final, NamedTuple

from tutor import credit
from tutor.curriculum import rules
from tutor.curriculum.errors import RequestError
from tutor.curriculum.no_card import due_in_subject
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tutor.curriculum.fold import Fold
    from tutor.relay.context import RequestContext

type Json = Any
_logger = logging.getLogger(__name__)
REVIEW_MS: Final = 10 * 60_000


class Day(NamedTuple):
    """Today's local bounds and the clock, all in ms."""

    lo: int
    hi: int
    now: int

    def has(self, ms: object) -> bool:
        """Whether ``ms`` is a timestamp inside today."""
        return isinstance(ms, int) and self.lo <= ms < self.hi


def _rows(folder: str) -> Iterator[dict[str, Json]]:
    for path in sorted((data_dir() / folder).glob("*.json")):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            _logger.warning("%s/%s is unreadable", folder, path.name)
            continue
        if isinstance(row, dict):
            yield row


def _coach(step: dict[str, Json], day: Day, _ctx: RequestContext) -> bool:
    rows = _rows("lc_sessions")
    return any(
        r.get("slug") == step["target"] and day.has(r.get("exit_ms")) for r in rows
    )


def _lesson(step: dict[str, Json], day: Day, _ctx: RequestContext) -> bool:
    rows = _rows("sql_lessons")
    return any(
        r.get("topic") == step["target"] and day.has(r.get("mastered_ms")) for r in rows
    )


def _finished(day: Day) -> list[int]:
    out = [
        r["result"].get("finished_ms")
        for r in _rows("mocks")
        if isinstance(r.get("result"), dict)
    ]
    return [ms for ms in out if day.has(ms)]


def _mock(step: dict[str, Json], day: Day, _ctx: RequestContext) -> bool:
    finished = _finished(day)
    if step["target"] == "review":
        return any(day.now - ms >= REVIEW_MS for ms in finished)
    return bool(finished)


def _studied(fold: Fold, subject: str, day: Day) -> bool:
    for (subj, _), state in fold.cards.items():
        times = [state.taught_at, *state.new_at, *(at for at, _ in state.reviews)]
        if subj == subject and any(day.has(at) for at in times):
            return True
    return False


def _cards(step: dict[str, Json], day: Day, ctx: RequestContext) -> bool:
    cur, subject = ctx.engine.ctx, step["target"]
    try:
        plan = cur.subjects.plan(subject)
        cards = cur.subjects.cards(subject)
    except RequestError:  # a target that is not a subject id
        _logger.warning("plan step %s: %r is not a subject", step["id"], subject)
        return False
    if plan is None:
        return False
    fold = cur.fold()
    view = rules.View(subject, plan, cards)
    return due_in_subject(view, fold, day.now) == 0 and _studied(fold, subject, day)


_RULES: Final = {"coach": _coach, "sql_lesson": _lesson, "mock": _mock, "cards": _cards}


def auto_done(ctx: RequestContext, steps: list[dict[str, Json]]) -> list[str]:
    """Ids of ``steps`` the server saw done today (plan order)."""
    _, lo, hi = credit.local_day(ctx.now())
    day = Day(int(lo * 1000), int(hi * 1000), int(ctx.now() * 1000))
    return [
        s["id"] for s in steps if (rule := _RULES.get(s["kind"])) and rule(s, day, ctx)
    ]
