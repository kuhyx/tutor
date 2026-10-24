# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The engine's chores: repair, backfill, resume after a restart, a new card's clock.

``Engine`` mixes this in; the attributes it needs are declared for the type
checker.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from tutor import backfill, leftover, repair, resume
from tutor.clock import EngagementClock
from tutor.conversation import Conversation

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.clock import BlockReady
    from tutor.store import Store


class Upkeep:
    """``repair_done_cards``, ``backfill_today``, ``resume_latest``."""

    if TYPE_CHECKING:
        store: Store
        _credit: Callable[[list[BlockReady], str], list[dict[str, Any]]]
        _set_today: Callable[[int], None]
        resume_path: Callable[[Path], bool]
        time: Callable[[], float]

        @property
        def minutes_today(self) -> int:
            """Today's ledger total (``CardFlow``)."""

    def repair_done_cards(self) -> list[tuple[str, str]]:
        """Run the one-off card_done repair (see ``repair``)."""
        return repair.repair_done_cards(self.store)

    def backfill_today(self) -> None:
        """Credit minutes today's transcripts earned but never got paid (idempotent)."""
        paid = backfill.backfill_day(
            self.store.root / "sessions",
            time.strftime("%Y%m%d"),
            self._credit,
            self.store.log,
        )
        self._set_today(max(self.minutes_today, paid))

    def resume_latest(self) -> bool:
        """Pick today's newest session back up after a restart (see ``resume_path``)."""
        path = resume.latest_today(
            self.store.root / "sessions", time.strftime("%Y%m%d")
        )
        return self.resume_path(path) if path else False

    def _opening(self, sid: str, card_id: str) -> tuple[Conversation, dict[str, Any]]:
        """A new card's conversation and ``start`` event.

        Its clock opens with the day's part minute so far (``leftover.seed``),
        logged as ``carry_in`` so replay reproduces it.
        """
        carry_in = leftover.seed(self.store.root / "sessions", sid[:8])
        clock = EngagementClock(self.time(), carry_in=carry_in)
        start = {"type": "start", "card": card_id, "carry_in": carry_in}
        return Conversation(sid, card_id, clock), start
