# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The engine's chores: repair, backfill, resume after a restart, a new card's clock.

``Engine`` mixes this in; the attributes it needs are declared for the type
checker.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from tutor import backfill, leftover, repair, resume, unit_credit
from tutor.clock import EngagementClock
from tutor.conversation import Conversation
from tutor.curriculum import module_state
from tutor.curriculum.source import transcript_subject

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.cards import Card
    from tutor.clock import BlockReady
    from tutor.curriculum.context import Context
    from tutor.curriculum.source import CardSource
    from tutor.store import Store


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
        """The default writer: the live session's rows name its card's module (C1).

        Backfill pays other sessions through it too; the card on screen is not
        theirs, so their rows stay untagged (never the wrong module).
        """
        card = self.card if sid == self.session_id else None
        subject = self.source.subject
        return unit_credit.teaching_units(
            units, sid, now=self.time(), subject=subject, card=card
        )

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
        """Sign the done state of every LeetCode / SQL module not on file (C2)."""
        module_state.backfill(self.store.root, self.time())

    def resume_latest(self) -> bool:
        """Pick today's newest session back up after a restart (see ``resume_path``)."""
        path = resume.latest_today(
            self.store.root / "sessions", time.strftime("%Y%m%d")
        )
        if path is None or transcript_subject(path) in self.ctx.archived():
            return False  # none today, or its subject is archived since
        return self.resume_path(path)

    def _opening(self, sid: str, card_id: str) -> tuple[Conversation, dict[str, Any]]:
        """A new card's conversation and ``start`` event.

        Its clock opens with the day's part minute so far (``leftover.seed``),
        logged as ``carry_in`` so replay reproduces it.
        """
        carry_in = leftover.seed(self.store.root / "sessions", sid[:8])
        clock = EngagementClock(self.time(), carry_in=carry_in)
        start = {"type": "start", "card": card_id, "carry_in": carry_in}
        return Conversation(sid, card_id, clock), start
