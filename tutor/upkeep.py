# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The engine's start-of-day chores: repair, backfill, resume after a restart.

``Engine`` mixes this in; the attributes it needs are declared for the type
checker.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from tutor import backfill, repair, resume

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
