# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Re-fold the log and move every approved subject forward.

:func:`fold_and_advance` is what the worker calls after the log changed
(and before each request): it writes each module's ``recall`` and ``status``
(``ready`` -> ``mastered``, ``locked`` -> ``generating``), sets a subject
``completed`` once every module is mastered, and returns the modules waiting
for cards. It never generates cards itself (that is minutes of model time):
the worker runs ``cardgen.generate`` for each pending module on the build
lane. :func:`pending` lists them again after a restart, so a module left
``generating`` by a crash is picked up.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from tutor.curriculum import rules
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.fold import Fold


def pending(ctx: Context) -> list[tuple[str, str]]:
    """``(subject, module)`` for every module in ``generating``."""
    out = []
    for subject in ctx.subjects.subjects():
        plan = ctx.subjects.plan(subject)
        if plan is not None and plan.status == "approved":
            out += [(subject, m.id) for m in plan.modules if m.status == "generating"]
    return out


def _advance(ctx: Context, subject: str, folded: Fold) -> bool:
    """One subject; True when something was written."""
    with LOCK:
        meta = ctx.subjects.need_meta(subject)
        plan = ctx.subjects.plan(subject)
        if plan is None or plan.status != "approved":
            return False
        before = asdict(plan)
        view = rules.View(subject, plan, ctx.subjects.cards(subject))
        rules.advance_statuses(view, folded)
        finished = meta.status == "active" and rules.completed(plan)
        if finished:
            meta.status = "completed"
        if not finished and asdict(plan) == before:
            return False
        ctx.subjects.commit(subject, meta, Change(plan=plan))
        return True


def fold_and_advance(ctx: Context) -> dict[str, Any]:
    """Re-fold, update every subject; returns what changed and what to generate.

    ``{"changed": [subject...], "generate": [[subject, module]...]}``.
    """
    folded = ctx.fold()
    changed = [s for s in ctx.subjects.subjects() if _advance(ctx, s, folded)]
    return {"changed": changed, "generate": [list(p) for p in pending(ctx)]}
