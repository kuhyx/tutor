# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The PC mirror of the RTDB event log: ``$TUTOR_DATA/log.jsonl``.

One event per line, each carrying the ``dev`` and ``eid`` it has in RTDB
(``log/{dev}/{eid}``). Appending is idempotent on ``(dev, eid)``, so the
relay worker can mirror the same remote events again after a restart. Events
from RTDB are untrusted: :func:`parse` keeps only well-formed ones and drops
unknown keys. The worker's own ``taught``/``untaught`` (and ``cap_lift``)
events are written here first (the commit point) and published by the relay
worker. ``cap_lift`` and ``new_cap`` name no subject or card
(``DOCS-contract-curriculum.md`` §4/§6).
"""

from __future__ import annotations

from datetime import date
import json
import logging
import re
import threading
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.ids import ulid, valid_eid, valid_id

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

CAP_LIFT: Final = "cap_lift"  # {"day"}: the daily new cap is off that local day
NEW_CAP: Final = "new_cap"  # {"n"}: Settings' daily new cap, latest ``at`` wins
GLOBAL_KINDS: Final = frozenset({CAP_LIFT, NEW_CAP})  # no subject or card
REVIEW_UNDO: Final = "review_undo"  # {"of"}: that review eid never counts
KINDS: Final = frozenset(
    {"review", REVIEW_UNDO, "flag", "taught", "untaught", *GLOBAL_KINDS}
)
CAP_MIN: Final = 1
CAP_MAX: Final = 200
DAY: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
MAX_REASON: Final = 500
RATINGS: Final = frozenset({1, 2, 3, 4})
DRILL: Final = "drill"  # review ``src``: a PC drill pick (never counts as reviewed)
_LOCK: Final = threading.Lock()
_logger = logging.getLogger(__name__)


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class _MalformedError(ValueError):
    """An event that breaks the contract; :func:`parse` logs why and drops it."""


def _review(raw: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    rating = _int(raw.get("r"))
    if rating is None or rating not in RATINGS:
        msg = f"rating {raw.get('r')!r}"
        raise _MalformedError(msg)
    event["r"] = rating
    event["rev"] = _int(raw.get("rev")) or 1
    if (dur := _int(raw.get("dur_ms"))) is not None:
        event["dur_ms"] = dur
    if raw.get("src") == DRILL:  # untrusted: the one known source only
        event["src"] = DRILL
    return event


def _card_event(raw: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """A per-card event: ``head`` plus ``s``/``c`` and its kind's fields."""
    if not valid_id(raw.get("s")) or not valid_id(raw.get("c")):
        msg = "bad subject or card id"
        raise _MalformedError(msg)
    event = {**head, "s": raw["s"], "c": raw["c"]}
    kind = head["k"]
    if kind == "review":
        return _review(raw, event)
    if kind == REVIEW_UNDO:
        if not valid_eid(raw.get("of")):
            msg = f"of {raw.get('of')!r}"
            raise _MalformedError(msg)
        event["of"] = raw["of"]
    elif kind == "flag":
        event["rev"] = _int(raw.get("rev")) or 1
        reason = raw.get("reason")
        event["reason"] = reason[:MAX_REASON] if isinstance(reason, str) else ""
    elif kind == "taught" and isinstance(raw.get("session"), str):
        event["session"] = raw["session"]
    return event


def _day(value: object) -> str:
    """``value`` if it is ``YYYY-MM-DD`` naming a real date."""
    msg = f"day {value!r}"
    if not isinstance(value, str) or not DAY.fullmatch(value):
        raise _MalformedError(msg)
    try:
        date.fromisoformat(value)
    except ValueError as err:  # 2026-02-30: the shape is right, the date is not
        raise _MalformedError(msg) from err
    return value


def _global_event(raw: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """``cap_lift`` (``day``) / ``new_cap`` (``n`` in 1..200): no subject or card."""
    if head["k"] == CAP_LIFT:
        return {**head, "day": _day(raw.get("day"))}
    n = _int(raw.get("n"))
    if n is None or not CAP_MIN <= n <= CAP_MAX:
        msg = f"n {raw.get('n')!r}"
        raise _MalformedError(msg)
    return {**head, "n": n}


def parse(dev: str, eid: str, raw: object) -> dict[str, Any] | None:
    """A clean event, or None (logged) when ``raw`` breaks the contract."""
    if not isinstance(raw, dict) or not valid_eid(eid) or not dev:
        return None
    kind, at = raw.get("k"), _int(raw.get("at"))
    if kind not in KINDS or at is None or at <= 0:
        _logger.warning("dropped event %s/%s: bad kind or time", dev, eid)
        return None
    head = {"dev": dev, "eid": eid, "k": kind, "at": at}
    try:
        if kind in GLOBAL_KINDS:
            return _global_event(raw, head)
        return _card_event(raw, head)
    except _MalformedError as err:
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


def cap_lift_event(day: str, *, dev: str, at: int) -> dict[str, Any]:
    """The worker's ``cap_lift`` for local ISO ``day``, fresh eid."""
    return {"dev": dev, "eid": ulid(at), "k": CAP_LIFT, "day": day, "at": at}


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
