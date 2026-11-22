# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What every curriculum operation runs against, injectable for tests.

``Context(data_dir)`` is the real thing: the wall clock in ms, the isolated
model on its two tiers (``model``: Sonnet for what repeats, ``draft``: Fable
for writing cards; ``tutor.tiers``), the MediaWiki fetch and the excerpt
check. Tests replace any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import time
from typing import TYPE_CHECKING, Any

from tutor import sources
from tutor.curriculum import modelcall, wiki
from tutor.curriculum.eventlog import archived_subjects
from tutor.curriculum.fold import Fold, fold, without
from tutor.curriculum.ids import device_id
from tutor.curriculum.module_state import WatchedLog, WatchedStore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.curriculum.eventlog import EventLog
    from tutor.curriculum.subject_store import SubjectStore

    ModelFn = Callable[[str, str, dict[str, Any]], dict[str, Any]]
    CheckFn = Callable[[str, str, str], sources.Mismatch | None]


def wall_ms() -> int:
    """Unix time in ms."""
    return int(time.time() * 1000)


@dataclass
class Context:
    """Data dir plus the clock, model, fetch and excerpt check to use."""

    data_dir: Path
    clock: Callable[[], int] = wall_ms
    model: ModelFn = modelcall.ask_repeat
    draft: ModelFn = modelcall.ask_draft  # writes cards; never a fallback
    fetch: Callable[[str], bytes] = wiki.http_get
    check: CheckFn = sources.check_excerpt
    # A source's plain text (fetched once, cached): what an added card quotes.
    text: Callable[[str], str] = sources.page_text
    device: str = field(default="")

    def __post_init__(self) -> None:
        """Resolve the device id (``$TUTOR_DATA/device_id``) when not given."""
        if not self.device:
            self.device = device_id(self.data_dir / "device_id")

    def drafting(self) -> Context:
        """This context with the draft tier as its model (card writing)."""
        return replace(self, model=self.draft)

    @property
    def subjects(self) -> SubjectStore:
        """The subject files; a card commit records module flips (C2)."""
        return WatchedStore(self.data_dir, self.clock)

    @property
    def log(self) -> EventLog:
        """The event log mirror; a taught / untaught records module flips (C2)."""
        return WatchedLog(self.data_dir, self.clock)

    def fold(self) -> Fold:
        """The fold of the whole local log, archived subjects masked out."""
        events = self.log.read()
        return without(fold(events), archived_subjects(events))

    def archived(self) -> set[str]:
        """Subjects archived now (``subject_archive``, not undone)."""
        return archived_subjects(self.log.read())
