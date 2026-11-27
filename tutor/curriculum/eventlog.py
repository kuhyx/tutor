# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The PC mirror of the RTDB event log: ``$TUTOR_DATA/log.jsonl``.

One event per line, each carrying the ``dev`` and ``eid`` it has in RTDB
(``log/{dev}/{eid}``). Appending is idempotent on ``(dev, eid)``, so the
relay worker can mirror the same remote events again after a restart. Events
from RTDB are untrusted: :func:`parse` keeps only well-formed ones and drops
unknown keys. The worker's own ``taught``/``untaught`` events are written
here first (the commit point) and published by the relay worker.
``cap_lift`` and ``new_cap`` (the daily cap, removed 2026-11-22) name no
subject or card and still parse, so old logs stay valid; nothing reads
them (``DOCS-contract-curriculum.md`` §4); ``subject_archive`` /
``subject_unarchive`` (worker) name a subject only (``DOCS-relay-kinds.md``).
``unchecked`` (``src`` read / free) marks a card taught without Claude, and
``checked`` clears that mark once Claude has checked it (``README.md``
"Fallback").
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.event_parts import (
    CAP_LIFT,
    MalformedError,
    as_int,
    global_event,
    subject_event,
)
from tutor.curriculum.ids import ulid, valid_eid, valid_id

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

NEW_CAP: Final = "new_cap"  # {"n"}: old daily cap setting, kept, unused
GLOBAL_KINDS: Final = frozenset({CAP_LIFT, NEW_CAP})  # no subject or card
REVIEW_UNDO: Final = "review_undo"  # {"of"}: that review eid never counts
ARCHIVE: Final = "subject_archive"  # {"s"}: hidden and unlearned (worker)
UNARCHIVE: Final = "subject_unarchive"  # {"s"}: back, state intact (worker)
SUBJECT_KINDS: Final = frozenset({ARCHIVE, UNARCHIVE})  # a subject, no card
UNCHECKED: Final = "unchecked"  # {"src"}: taught without Claude, check it
CHECKED: Final = "checked"  # Claude checked it: the unchecked mark is gone
KINDS: Final = frozenset(
    {"review", REVIEW_UNDO, "flag", "taught", "untaught", UNCHECKED, CHECKED}
    | GLOBAL_KINDS
    | SUBJECT_KINDS
)
MAX_REASON: Final = 500
RATINGS: Final = frozenset({1, 2, 3, 4})
DRILL: Final = "drill"  # review ``src``: a PC drill pick (never counts as reviewed)
CHECKIN: Final = "checkin"  # review ``src``: a focus check-in card (an ordinary review)
SOURCES: Final = frozenset({DRILL, CHECKIN})
READ: Final = "read"  # unchecked ``src``: read mode (no model)
FREE: Final = "free"  # unchecked ``src``: a free-model chat (OmniRoute)
UNCHECKED_SOURCES: Final = frozenset({READ, FREE})
_LOCK: Final = threading.Lock()
_logger = logging.getLogger(__name__)


def _review(raw: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    rating = as_int(raw.get("r"))
    if rating is None or rating not in RATINGS:
        msg = f"rating {raw.get('r')!r}"
        raise MalformedError(msg)
    event["r"] = rating
    event["rev"] = as_int(raw.get("rev")) or 1
    if (dur := as_int(raw.get("dur_ms"))) is not None:
        event["dur_ms"] = dur
    if (src := raw.get("src")) in SOURCES:  # untrusted: the known sources only
        event["src"] = src
    return event


def _card_event(raw: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """A per-card event: ``head`` plus ``s``/``c`` and its kind's fields."""
    if not valid_id(raw.get("s")) or not valid_id(raw.get("c")):
        msg = "bad subject or card id"
        raise MalformedError(msg)
    event = {**head, "s": raw["s"], "c": raw["c"]}
    kind = head["k"]
    if kind == "review":
        return _review(raw, event)
    if kind == REVIEW_UNDO:
        if not valid_eid(raw.get("of")):
            msg = f"of {raw.get('of')!r}"
            raise MalformedError(msg)
        event["of"] = raw["of"]
    elif kind == "flag":
        event["rev"] = as_int(raw.get("rev")) or 1
        reason = raw.get("reason")
        event["reason"] = reason[:MAX_REASON] if isinstance(reason, str) else ""
    elif kind == UNCHECKED:
        src = raw.get("src")
        event["src"] = src if src in UNCHECKED_SOURCES else READ
    elif kind == "taught" and isinstance(raw.get("session"), str):
        event["session"] = raw["session"]
    return event


def parse(dev: str, eid: str, raw: object) -> dict[str, Any] | None:
    """A clean event, or None (logged) when ``raw`` breaks the contract."""
    if not isinstance(raw, dict) or not valid_eid(eid) or not dev:
        return None
    kind, at = raw.get("k"), as_int(raw.get("at"))
    if kind not in KINDS or at is None or at <= 0:
        _logger.warning("dropped event %s/%s: bad kind or time", dev, eid)
        return None
    head = {"dev": dev, "eid": eid, "k": kind, "at": at}
    try:
        if kind in GLOBAL_KINDS:
            return global_event(raw, head)
        if kind in SUBJECT_KINDS:
            return subject_event(raw, head)
        return _card_event(raw, head)
    except MalformedError as err:
        _logger.warning("dropped %s %s/%s: %s", kind, dev, eid, err)
        return None


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
    """A worker event (``taught``, ``untaught``, ``checked``) on ``ref``.

    ``ref`` = (subject, card), with a fresh eid. ``unchecked`` events carry a
    source tag: build them with :func:`unchecked_event`.
    """
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


def unchecked_event(
    ref: tuple[str, str], *, dev: str, at: int, src: str = READ
) -> dict[str, Any]:
    """An ``unchecked`` event on ``ref``; ``src`` is in :data:`UNCHECKED_SOURCES`."""
    return {**worker_event(UNCHECKED, ref, dev=dev, at=at), "src": src}


def review_event(
    ref: tuple[str, str], rating: int, *, dev: str, span: tuple[int, int], rev: int
) -> dict[str, Any]:
    """A ``review`` of ``ref`` in the app's shape (``log_event.dart``), fresh eid.

    ``span`` is (shown, answered) in unix ms: ``at`` is the answer. The app
    sends no ``src``; the drill adds ``"src": DRILL`` to its own.
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


def archived_subjects(events: Iterable[dict[str, Any]]) -> set[str]:
    """Subjects whose latest archive event by ``(at, eid)`` is ``subject_archive``."""
    marks = sorted(
        (e for e in events if e["k"] in SUBJECT_KINDS),
        key=lambda e: (e["at"], e["eid"]),
    )
    latest = {e["s"]: e["k"] == ARCHIVE for e in marks}
    return {subject for subject, on in latest.items() if on}
