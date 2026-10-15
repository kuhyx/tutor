# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""When Claude was unavailable: the windows the drill and Anki credit key on.

``<data dir>/unavailable.jsonl``, one window per line:
``{"start": <unix s>, "end": <unix s>, "reason": <REASONS>}``. ``end`` is the
rate limit's ``resets_at``; an error with no reset time gets
:data:`DEFAULT_SPAN` and is extended by each later failure. Windows may
overlap; readers take the union. Append-only, so a crash never loses one.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Final

from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

REASONS: Final = frozenset({"rate_limit", "overloaded", "network"})
# How long an unavailability with no reset time is assumed to last from its failure.
DEFAULT_SPAN: Final = 15 * 60
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Window:
    """``start <= t < end`` (unix seconds) Claude was unavailable for ``reason``."""

    start: int
    end: int
    reason: str

    def covers(self, at: float) -> bool:
        """Whether unix time ``at`` falls inside the window."""
        return self.start <= at < self.end


def path(root: Path | None = None) -> Path:
    """The outage log under ``root`` (default: the data dir)."""
    return (root or data_dir()) / "unavailable.jsonl"


def record(
    reason: str, now: float, resets_at: float | None = None, root: Path | None = None
) -> Window:
    """Append the window starting ``now``; ``resets_at`` ends it if known."""
    if reason not in REASONS:
        msg = f"unknown unavailable reason {reason!r}"
        raise ValueError(msg)
    start = int(now)
    end = int(resets_at) if resets_at and resets_at > now else start + DEFAULT_SPAN
    window = Window(start, end, reason)
    target = path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = {"start": window.start, "end": window.end, "reason": reason}
    with target.open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")
    return window


def windows(root: Path | None = None) -> list[Window]:
    """Every recorded window, oldest first; malformed lines are logged, skipped."""
    target = path(root)
    if not target.is_file():
        return []
    found: list[Window] = []
    for number, raw in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        try:
            item = json.loads(raw)
            window = Window(int(item["start"]), int(item["end"]), str(item["reason"]))
        except ValueError, KeyError, TypeError:
            _logger.warning("unavailable.jsonl:%d unreadable, skipped", number)
            continue
        found.append(window)
    return sorted(found, key=lambda w: w.start)


def current(now: float, root: Path | None = None) -> Window | None:
    """The window covering ``now`` that ends latest, or None if Claude is up."""
    live = [w for w in windows(root) if w.covers(now)]
    return max(live, key=lambda w: w.end) if live else None


def unavailable_at(at: float, found: list[Window]) -> bool:
    """Whether ``at`` falls in any of ``found`` (from :func:`windows`)."""
    return any(w.covers(at) for w in found)
