# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Read mode: learning new cards with no model, for when Claude is out.

:meth:`ReadMode.next` shows the next untaught card (``pick.untaught``: open,
unlocked modules C3 does not refuse; cards not suspended, flagged or held by
``requires``) of a subject, or of every subject in name order. It ignores
the module gate's review hold (reading may start a module a session could
not yet), but never opens a new module while an earlier one holds cards
read without Claude and not checked yet: new reading does not pile up on
unchecked cards (spec Q10/Q11). Only
curriculum subjects are read (the unmigrated deck has no event log).

:meth:`ReadMode.rate` ("got_it" / "again") writes, 1 ms apart so the fold's
``(at, eid)`` order is fixed: ``taught`` (``SubjectSource.mark``, session
``read-<id>``), ``unchecked`` (``src: read``: the next Claude session checks
the card first), and for "again" a ``review`` rated Again with no ``src``
(the worker's reviews fold as drill picks): due in a day instead of two.
Pay is the drill's (:mod:`tutor.model_free_pay`); its rows name the card's
subject and module with no ``activity``, as a lesson minute. The open
prompt lives in memory only; a stale one is ``PromptGoneError``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import ledger_pay, unavailable
from tutor.curriculum import card_rules
from tutor.curriculum import pick as picking
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import READ, review_event, unchecked_event
from tutor.curriculum.ids import ulid
from tutor.curriculum.no_card import unchecked_of
from tutor.curriculum.source import SubjectSource
from tutor.drill import AGAIN, PromptGoneError
from tutor.model_free_pay import Run, Runs, credited

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tutor.cards import Card
    from tutor.curriculum.context import Context
    from tutor.curriculum.fold import Fold
    from tutor.curriculum.records import Module
    from tutor.curriculum.rules import View
    from tutor.store import Store

GOT_IT: Final = "got_it"
AGAIN_RATING: Final = "again"
RATINGS: Final = frozenset({GOT_IT, AGAIN_RATING})
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Prompt:
    """One open card to read: which card, its module and rev, when shown."""

    subject: str
    module: str
    card: Card
    rev: int
    prompt_id: str
    shown_at: float


class ReadMode:
    """Read mode of one data dir; at most one prompt is open at a time."""

    def __init__(self, store: Store, ctx: Context) -> None:
        """``ctx.device`` signs the events (the worker's own log)."""
        self.store, self.ctx = store, ctx
        self.pending: Prompt | None = None
        self.runs = Runs(store.root, "read")

    def next(self, subject: str | None, at: float) -> dict[str, Any]:
        """The next card to read (it replaces any open one), or ``{"empty": True}``."""
        found = self._first(subject, at)
        if found is None:
            return {"empty": True}
        self.pending = found
        card = found.card
        self.runs.log(
            self.runs.run_for(at),
            {"type": "prompt", "id": found.prompt_id, "card": card.id},
        )
        window = unavailable.current(at)
        return {
            "prompt_id": found.prompt_id,
            "card": {
                "subject": found.subject,
                "id": card.id,
                "module": found.module,
                "front": card.front,
                "back": card.back,
                "excerpt": card.excerpt,
                "source": card.source,
            },
            "today": self.runs.today(at),
            "unavailable": window and {"until": window.end, "reason": window.reason},
        }

    def rate(self, prompt_id: str, rating: str, at: float) -> dict[str, Any]:
        """Mark the card taught and unchecked (Again: also a review); credit."""
        prompt, run = self.pending, self.runs.current
        if prompt is None or run is None or prompt.prompt_id != prompt_id:
            msg = "that card is no longer open to read; ask for the next one"
            raise PromptGoneError(msg)
        if rating not in RATINGS:
            msg = f"{rating!r} is not a read rating"
            raise ValueError(msg)
        self.pending = None
        self._write(prompt, run, rating, at)
        taught = ledger_pay.Taught(subject=prompt.subject, module=prompt.module)
        rows = self.runs.accrue(run, (prompt.shown_at, at), taught)
        self.runs.log(run, {"type": "rate", "card": prompt.card.id, "rating": rating})
        return {
            "rated": rating,
            "minute_credited": credited(rows),
            "today": self.runs.today(at),
        }

    def _write(self, prompt: Prompt, run: Run, rating: str, at: float) -> None:
        """``taught`` at the clock's now, then ``unchecked``, then Again's review."""
        taught_at = self.ctx.clock()  # read once: the next events key off it
        pinned = replace(self.ctx, clock=lambda: taught_at)
        source = SubjectSource(self.store, pinned, prompt.subject)
        source.mark(prompt.card.id, run.session_id, done=True)
        ref, dev = (prompt.subject, prompt.card.id), self.ctx.device
        events = [unchecked_event(ref, dev=dev, at=taught_at + 1, src=READ)]
        if rating == AGAIN_RATING:
            end = taught_at + 2
            gap = max(0, int((at - prompt.shown_at) * 1000))
            span = (end - gap, end)
            events.append(review_event(ref, AGAIN, dev=dev, span=span, rev=prompt.rev))
        self.ctx.log.append(events)

    def _first(self, subject: str | None, at: float) -> Prompt | None:
        """The first card to read of ``subject`` (None: of every subject)."""
        names = [subject] if subject else self.ctx.subjects.subjects()
        archived, fold = self.ctx.archived(), self.ctx.fold()
        for name in names:
            if name in archived or self.ctx.subjects.meta(name) is None:
                continue
            try:
                view = SubjectSource(self.store, self.ctx, name).view()
            except RequestError as err:  # a subject still drafting its plan
                _logger.warning("read mode skips %s: %s", name, err.message)
                continue
            found = next(_readable(view, fold, int(at * 1000)), None)
            if found is not None:
                cid, module = found
                rec = view.cards[cid]
                card = card_rules.as_card(cid, rec, module)
                pid = ulid(int(at * 1000))
                return Prompt(name, module.id, card, rec.rev, pid, at)
        return None


def _readable(view: View, fold: Fold, now_ms: int) -> Iterator[tuple[str, Module]]:
    """``pick.untaught`` up to the first new module held by unchecked cards."""
    for cid, module in picking.untaught(view, fold):
        if not picking.started(view, fold, module.id):
            ahead = picking.gate(view, fold, now_ms, before=module.id)
            if unchecked_of(view, fold, ahead.cards):
                return
        yield cid, module
