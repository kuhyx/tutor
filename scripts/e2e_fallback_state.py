#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The sandbox copy F33 seeds (``e2e_fallback_seed.py``): views, dues, events.

:class:`Seeder` reads every unarchived subject's plan and cards once and
writes the events the branches need: worker ``taught``/``untaught`` and
``subject_archive`` as the sandbox worker, drill reviews and flags as a
fresh "app" device. :func:`outage` writes the open outage window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final
import uuid

from e2e_seed import GAP_MS, GOOD, SeedError, _sandboxed

from tutor import unavailable
from tutor.curriculum import pick, rules
from tutor.curriculum.archive import subject_event
from tutor.curriculum.context import Context
from tutor.curriculum.eventlog import ARCHIVE, DRILL, review_event, worker_event

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.fold import Fold

OUTAGE_S: Final = 2 * 3600
# Nothing may come due while a flow runs: past the window and the sandbox's hour.
MARGIN_MS: Final = 3 * 3_600_000
EASY: Final = 4


def outage(data: Path, reason: str, now: float) -> unavailable.Window:
    """Record an open window from ``now`` to :data:`OUTAGE_S` later."""
    _sandboxed(data)
    return unavailable.record(reason, now, now + OUTAGE_S, root=data)


class Seeder:
    """One sandbox copy: the sandbox worker's id, a fresh "app" id, now."""

    def __init__(self, data: Path, subject: str, now: int) -> None:
        """``now`` in unix ms; refuses the real data dir."""
        _sandboxed(data)
        self.data, self.subject, self.now = data, subject, now
        self.ctx = Context(data, device=str(uuid.uuid4()))
        self.worker = (data / "device_id").read_text(encoding="utf-8").strip()
        self.views = {
            n: v for n in self.ctx.subjects.subjects() if (v := self._view(n))
        }
        if subject not in self.views:
            msg = f"{subject} has no plan in the sandbox"
            raise SeedError(msg)

    def _view(self, name: str) -> rules.View | None:
        plan = self.ctx.subjects.plan(name)
        return (
            None
            if plan is None
            else rules.View(name, plan, self.ctx.subjects.cards(name))
        )

    @property
    def target(self) -> rules.View:
        """The subject the flow starts in."""
        return self.views[self.subject]

    def due(self, view: rules.View, until: int) -> list[str]:
        """``view``'s counted cards due at or before ``until`` (ms)."""
        folded = self.ctx.fold()
        out = []
        for cid, rec in view.cards.items():
            state = folded.card(view.subject, cid)
            sched = state.fsrs_state()
            if rec.suspended or state.flagged(rec.rev) or sched is None:
                continue
            if sched["due"] <= until:
                out.append(cid)
        return out

    def readable(self) -> list[str]:
        """S's readable cards in the first module read mode would open."""
        found = list(pick.untaught(self.target, self.ctx.fold()))
        first = found[0][1].id if found else ""
        return [cid for cid, module in found if module.id == first]

    def drafted(self, folded: Fold) -> list[tuple[str, int]]:
        """``(card, rev)`` of S's open modules, flagged and suspended ones aside.

        Open by status (``ready`` / ``mastered``, what the plan shows), which
        is wider than ``pick.teachable``: a module unlocked only by its taught
        cards stays open in the plan once they are untaught.
        """
        view = self.target
        return [
            (cid, rec.rev)
            for module in view.plan.modules
            if module.status in rules.OPEN
            for cid, rec in view.module_cards(module.id)
            if not rec.suspended and not folded.card(view.subject, cid).flagged(rec.rev)
        ]

    def worker_events(self, kind: str, cards: list[str], at: int) -> None:
        """One worker ``kind`` event per card of S at ``at``."""
        ev = [
            worker_event(kind, (self.subject, c), dev=self.worker, at=at) for c in cards
        ]
        self.ctx.log.append(ev)

    def clear_due(self, *, keep: str = "") -> int:
        """Drill-review every card due within the margin (``keep`` aside).

        Returns how many cards it reviewed (Easy follows Good on any still due).
        """
        cleared: set[tuple[str, str]] = set()
        for step, rating in enumerate((GOOD, EASY)):
            at = self.now - GAP_MS + step * 5000
            events = [
                {
                    **review_event(
                        (n, c),
                        rating,
                        dev=self.ctx.device,
                        span=(at - 5000, at),
                        rev=view.cards[c].rev,
                    ),
                    "src": DRILL,
                }
                for n, view in self.views.items()
                if n != keep
                for c in self.due(view, self.now + MARGIN_MS)
            ]
            self.ctx.log.append(events)
            cleared |= {(e["s"], e["c"]) for e in events}
        left = [
            (n, c)
            for n, v in self.views.items()
            if n != keep
            for c in self.due(v, self.now + MARGIN_MS)
        ]
        if left:
            msg = f"still due after Good and Easy: {left[:5]}"
            raise SeedError(msg)
        return len(cleared)

    def archive_others(self) -> list[str]:
        """Archive every subject but S; returns their names."""
        others = [n for n in self.views if n != self.subject]
        self.ctx.log.append(
            [subject_event(ARCHIVE, n, dev=self.worker, at=self.now) for n in others]
        )
        self.views = {self.subject: self.target}
        return others
