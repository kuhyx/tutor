# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The PC mirror of the RTDB event log: ``$TUTOR_DATA/log.jsonl``.

One event per line, each carrying the ``dev`` and ``eid`` it has in RTDB
(``log/{dev}/{eid}``). Appending is idempotent on ``(dev, eid)``, so the
relay worker can mirror the same remote events again after a restart. Events
from RTDB are untrusted: :func:`parse` keeps only well-formed ones and drops
unknown keys. The worker's own ``taught``/``untaught`` events are written
here first (the commit point) and published by the relay worker.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.ids import ulid, valid_eid, valid_id

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

KINDS: Final = frozenset({"review", "flag", "taught", "untaught"})
MAX_REASON: Final = 500
RATINGS: Final = frozenset({1, 2, 3, 4})
_LOCK: Final = threading.Lock()
_logger = logging.getLogger(__name__)


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def parse(dev: str, eid: str, raw: object) -> dict[str, Any] | None:
    """A clean event, or None (logged) when ``raw`` breaks the contract."""
    if not isinstance(raw, dict) or not valid_eid(eid) or not dev:
        return None
    kind, at = raw.get("k"), _int(raw.get("at"))
    if kind not in KINDS or at is None or at <= 0:
        _logger.warning("dropped event %s/%s: bad kind or time", dev, eid)
        return None
    if not valid_id(raw.get("s")) or not valid_id(raw.get("c")):
        _logger.warning("dropped event %s/%s: bad subject or card id", dev, eid)
        return None
    event: dict[str, Any] = {
        "dev": dev,
        "eid": eid,
        "k": kind,
        "s": raw["s"],
        "c": raw["c"],
        "at": at,
    }
    rev = _int(raw.get("rev"))
    if kind == "review":
        rating = _int(raw.get("r"))
        if rating is None or rating not in RATINGS:
            _logger.warning("dropped review %s/%s: rating %r", dev, eid, raw.get("r"))
            return None
        event["r"] = rating
        event["rev"] = rev or 1
        if (dur := _int(raw.get("dur_ms"))) is not None:
            event["dur_ms"] = dur
    elif kind == "flag":
        event["rev"] = rev or 1
        reason = raw.get("reason")
        event["reason"] = reason[:MAX_REASON] if isinstance(reason, str) else ""
    elif kind == "taught" and isinstance(raw.get("session"), str):
        event["session"] = raw["session"]
    return event


class EventLog:
    """``log.jsonl`` under the data dir."""

    def __init__(self, root: Path) -> None:
        """``root`` is the data dir."""
        self.path = root / "log.jsonl"

    def read(self) -> list[dict[str, Any]]:
        """Every stored event, in file order."""
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            raw = json.loads(line) if line.strip() else None
            if isinstance(raw, dict):
                clean = parse(str(raw.get("dev", "")), str(raw.get("eid", "")), raw)
                if clean is not None:
                    out.append(clean)
        return out

    def append(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Store the events not stored yet (by ``(dev, eid)``); returns those."""
        with _LOCK:
            seen = {(e["dev"], e["eid"]) for e in self.read()}
            fresh = []
            for raw in events:
                event = parse(str(raw.get("dev", "")), str(raw.get("eid", "")), raw)
                if event is None or (event["dev"], event["eid"]) in seen:
                    continue
                seen.add((event["dev"], event["eid"]))
                fresh.append(event)
            if fresh:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    for event in fresh:
                        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return fresh

    def mirror(self, dev: str, events: dict[str, object]) -> list[dict[str, Any]]:
        """Store one device's RTDB subtree (``eid -> event``); returns new ones."""
        return self.append(
            {**raw, "dev": dev, "eid": eid}
            for eid, raw in events.items()
            if isinstance(raw, dict)
        )


def worker_event(
    kind: str, ref: tuple[str, str], *, dev: str, at: int, session: str = ""
) -> dict[str, Any]:
    """A ``taught``/``untaught`` event on ``ref`` = (subject, card), fresh eid."""
    subject, card = ref
    event: dict[str, Any] = {
        "dev": dev,
        "eid": ulid(at),
        "k": kind,
        "s": subject,
        "c": card,
        "at": at,
    }
    if kind == "taught" and session:
        event["session"] = session
    return event


def review_event(
    ref: tuple[str, str], rating: int, *, dev: str, span: tuple[int, int], rev: int
) -> dict[str, Any]:
    """A ``review`` of ``ref`` in the app's shape (``log_event.dart``), fresh eid.

    ``span`` is (shown, answered) in unix ms: ``at`` is the answer.
    """
    subject, card = ref
    shown, at = span
    return {
        "dev": dev,
        "eid": ulid(at),
        "k": "review",
        "s": subject,
        "c": card,
        "r": rating,
        "at": at,
        "rev": rev,
        "dur_ms": max(0, at - shown),
    }
