# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Keep one module of drafted cards in stock per subject studied this week.

Read mode (Claude's limit used up) reads untaught drafted cards; a module
drafts its cards only when it unlocks, so an outage could leave nothing to
read. :func:`queue` pre-drafts, through the opt-in ``module_pregenerate``
path (:mod:`tutor.curriculum.pregen`), the first ``locked`` module in plan
order of every approved, not archived subject with a ``review`` or
``taught`` event in the last :data:`WINDOW_MS`, if that module has no cards.

One module in stock, never more: a subject is left alone while any module
is ``generating`` or already ``pregenerated`` (drafted and waiting, or a
failed pre-draft, which drafts just in time when it unlocks). Only the
first locked module is ever looked at, so a drafted one never makes the
next queue. The relay's ``PregenWork`` calls it while Claude is up and no
reply is in flight; ``cardgen`` keeps the drafted module ``locked``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import pregen
from tutor.curriculum.errors import RequestError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Plan

WINDOW_MS: Final = 7 * 24 * 3600 * 1000
STUDY_KINDS: Final = frozenset({"review", "taught"})
_logger = logging.getLogger(__name__)


def studied(events: Iterable[dict[str, Any]], now_ms: int) -> set[str]:
    """Subjects with a review or taught event in the window before ``now_ms``."""
    since = now_ms - WINDOW_MS
    return {e["s"] for e in events if e["k"] in STUDY_KINDS and e["at"] >= since}


def next_module(plan: Plan, cards: dict[str, CardRec]) -> str | None:
    """The module to draft ahead, or None (stock held, drafting, or nothing)."""
    if any(m.status == "generating" or m.pregenerated for m in plan.modules):
        return None
    first = next((m for m in plan.modules if m.status == "locked"), None)
    if first is None or any(c.module == first.id for c in cards.values()):
        return None
    return first.id


def picks(ctx: Context, now_ms: int) -> list[tuple[str, str]]:
    """``(subject, module)`` to queue now, at most one per subject."""
    active = studied(ctx.log.read(), now_ms)
    out = []
    for subject in ctx.subjects.subjects():  # archived ones are left out
        plan = ctx.subjects.plan(subject)
        if subject not in active or plan is None or plan.status != "approved":
            continue
        if (found := next_module(plan, ctx.subjects.cards(subject))) is not None:
            out.append((subject, found))
    return out


def queue(ctx: Context, now_ms: int) -> list[tuple[str, str]]:
    """Mark :func:`picks` ``generating`` + ``pregenerated``; returns those queued.

    A pick refused meanwhile (the plan changed under it) is logged and skipped.
    """
    queued = []
    for subject, found in picks(ctx, now_ms):
        body = {"subject": subject, "modules": [found]}
        try:
            pregen.module_pregenerate(body, ctx)
        except RequestError as err:
            _logger.warning("pre-drafting %s/%s refused: %s", subject, found, err)
            continue
        queued.append((subject, found))
    return queued
