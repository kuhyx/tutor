# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A model function that remembers every answer on disk, keyed by the prompt.

``Cached(ask, folder)`` is a ``ModelFn``: the same (system, prompt, schema)
is answered from ``folder`` without a call. That is what makes a redraft
resumable (a restarted unit replays its finished calls in milliseconds) and
lets the live run replay a dry run's replies. ``wait`` runs before every
REAL call: the live drainer blocks there while a learner's reply is in
flight. ``used`` lists the keys asked for, newest last, so a unit that
failed on a bad answer can forget exactly that answer (:meth:`forget`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import TYPE_CHECKING, Any

from tutor.curriculum.subject_store import read_json, write_json

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.curriculum.context import ModelFn


def _nothing() -> None:
    """The default ``wait``: never blocks."""


@dataclass
class Cached:
    """``ask`` with an on-disk answer cache in ``folder``."""

    ask: ModelFn
    folder: Path
    wait: Callable[[], None] = _nothing
    used: list[str] = field(default_factory=list)
    calls: int = 0  # real model calls made (cache misses)

    @staticmethod
    def key(system: str, prompt: str, schema: dict[str, Any]) -> str:
        """The cache key of one call."""
        text = json.dumps([system, prompt, schema], sort_keys=True)
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    def __call__(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """The cached answer, else a real call whose answer is stored."""
        key = self.key(system, prompt, schema)
        self.used.append(key)
        stored = read_json(self.folder / f"{key}.json", None)
        if isinstance(stored, dict):
            return stored
        self.wait()
        answer = self.ask(system, prompt, schema)
        self.calls += 1
        write_json(self.folder / f"{key}.json", answer)
        return answer

    def forget(self, key: str) -> None:
        """Drop one stored answer (the next identical call asks again)."""
        (self.folder / f"{key}.json").unlink(missing_ok=True)
