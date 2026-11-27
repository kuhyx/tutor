# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The engine's chores: repair, backfill, resume after a restart, a new card's clock.

``Engine`` mixes this in; the attributes it needs are declared for the type
checker.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from tutor import backfill, leftover, repair, resume, unit_credit
from tutor.clock import EngagementClock
from tutor.conversation import Conversation
from tutor.curriculum import module_state, review_due
from tutor.curriculum.deck_source import DEFAULT_SUBJECT
from tutor.curriculum.source import transcript_start, transcript_subject

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.cards import Card
    from tutor.clock import BlockReady
    from tutor.curriculum.context import Context
    from tutor.curriculum.source import CardSource
    from tutor.store import Store

_logger = logging.getLogger(__name__)


class Upkeep:
    """``repair_done_cards``, ``backfill_today``, ``record_module_states``, resume."""

    if TYPE_CHECKING:
        store: Store
        source: CardSource
        card: Card | None
        _credit: Callable[[list[BlockReady], str], list[dict[str, Any]]]
        _set_today: Callable[[int], None]
        _source_for: Callable[[str | None], CardSource]
        resume_path: Callable[[Path], bool]
        time: Callable[[], float]

        @property
        def minutes_today(self) -> int:
            """Today's ledger total (``CardFlow``)."""

        @property
        def session_id(self) -> str:
            """The live session's id (``Engine``)."""

        @property
        def ctx(self) -> Context:
            """The curriculum context (``CardFlow``)."""

    def repair_done_cards(self) -> list[tuple[str, str]]:
        """Run the one-off card_done repair (see ``repair``)."""
        return repair.repair_done_cards(self.store)

    def unrefuse_done_cards(self) -> list[tuple[str, str]]:
        """Re-apply the ``card_done`` the old gate refused (see ``repair``)."""
        return repair.unrefuse_done_cards(self.store, self._source_for)

    def _pay(self, units: list[BlockReady], sid: str) -> list[dict[str, Any]]:
        """The default writer: each row names its own session's subject and module (C1).

        Backfill pays other sessions through it too: their tags come from their
        own transcript's ``start``, never from the card on screen. The subject
        picks the row's kind (``ledger_pay.kind_for``), so a LeetCode session's
        backfilled minutes never pay the tutor bonus either.
        """
        if sid == self.session_id:
            subject, card = self.source.subject, self.card
        else:
            subject, card = self._own_card(sid)
        return unit_credit.teaching_units(
            units, sid, now=self.time(), subject=subject, card=card
        )

    def _own_card(self, sid: str) -> tuple[str, Card | None]:
        """A non-live session's subject and card, read from its transcript.

        The card is ``None`` (the rows then name the subject only) when it or
        its subject is gone or unreadable.
        """
        start = transcript_start(self.store.root / "sessions" / f"{sid}.jsonl")
        found = start.get("subject")
        subject = found if isinstance(found, str) else DEFAULT_SUBJECT
        try:
            cards = self._source_for(subject).cards()
        except (OSError, ValueError) as exc:  # RequestError: subject gone
            _logger.warning("backfill %s: no card of %s (%s)", sid, subject, exc)
            return subject, None
        return subject, next((c for c in cards if c.id == start.get("card")), None)

    def backfill_today(self) -> None:
        """Credit minutes today's transcripts earned but never got paid (idempotent)."""
        paid = backfill.backfill_day(
            self.store.root / "sessions",
            time.strftime("%Y%m%d"),
            self._credit,
            self.store.log,
        )
        self._set_today(max(self.minutes_today, paid))

    def record_module_states(self) -> None:
        """Sign the done state (C2) and the due reviews (C4) of every module."""
        module_state.backfill(self.store.root, self.time())
        review_due.backfill(self.store.root, self.time(), module_state.SUBJECTS)

    def resume_latest(self) -> bool:
        """Pick today's newest session back up after a restart (see ``resume_path``)."""
        path = resume.latest_today(
            self.store.root / "sessions", time.strftime("%Y%m%d")
        )
        if path is None or transcript_subject(path) in self.ctx.archived():
            return False  # none today, or its subject is archived since
        return self.resume_path(path)

    def _opening(
        self, sid: str, card_id: str, subject: str | None
    ) -> tuple[Conversation, dict[str, Any]]:
        """A new card's conversation and ``start`` event.

        Its clock opens with the day's part minute so far of ``subject``'s kind
        (``leftover.seed``), logged as ``carry_in`` so replay reproduces it.
        """
        carry_in = leftover.seed(self.store.root / "sessions", sid[:8], subject)
        clock = EngagementClock(self.time(), carry_in=carry_in)
        start = {"type": "start", "card": card_id, "carry_in": carry_in}
        return Conversation(sid, card_id, clock), start
