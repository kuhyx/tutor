# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Draft a module again once the Claude outage that failed it is over.

A module whose drafting hit Claude's spent usage limit (or another outage)
is ``failed`` with an outage ``error_kind`` (``codes.error_kind``), and the
app shows it with Retry. Card writers never fall back to the local model,
so without this the module stayed failed after the limit reset and study
ended on ``no_card_left`` until kuhy pressed Retry. :func:`retry` puts every
such module back to ``generating`` once no outage window is open;
:func:`tutor.curriculum.advance.pending` then hands it to the worker.

``recent`` (module -> when it was last put back) allows one retry per
:data:`tutor.unavailable.DEFAULT_SPAN`: an outage the window log missed
cannot loop the worker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import codes, unavailable
from tutor.curriculum.subject_store import LOCK, Change

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import Module

type Key = tuple[str, str]


def _spent(module: Module) -> bool:
    return module.status == "failed" and module.error_kind in codes.OUTAGE_KINDS


def retry(ctx: Context, now: float, recent: dict[Key, float]) -> list[Key]:
    """Put outage-failed modules back to ``generating``; returns them."""
    if unavailable.current(now) is not None:
        return []
    out: list[Key] = []
    archived = ctx.archived()
    for subject in ctx.subjects.subjects():
        if subject in archived:
            continue
        with LOCK:
            meta = ctx.subjects.need_meta(subject)
            plan = ctx.subjects.plan(subject)
            if plan is None or plan.status != "approved":
                continue
            due = [
                m
                for m in plan.modules
                if _spent(m)
                and now - recent.get((subject, m.id), -unavailable.DEFAULT_SPAN)
                > unavailable.DEFAULT_SPAN
            ]
            if not due:
                continue
            for found in due:
                found.status, found.error, found.error_kind = "generating", None, None
                recent[(subject, found.id)] = now
            ctx.subjects.commit(subject, meta, Change(plan=plan))
        out += [(subject, m.id) for m in due]
    return out
