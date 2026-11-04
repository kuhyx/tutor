# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Keep ``log/{own}`` readable from a cursor: re-mint stranded own events.

Every reader of ``log/{dev}`` (the app's ``EventLog.pull``, another worker's
``CurriculumSync.pull``) fetches only keys from the newest eid it has seen
(``startAt``). An own event stored with an eid below one stored before it
(minted from a backdated ``at`` by ``sql-cards`` or a seeding script in
another process) is never fetched by a reader that already passed that
key: the PC folds it, the phone does not. 2026-11-04: 37 cram and 25 SQL
cards were "37 due" on the PC and "Nothing due" in the app's Review.

:func:`copies` re-mints each such event under a fresh eid above every own
eid, same content and ``at``. For these kinds a second copy folds to the same
state (a re-``taught`` at the same ``at`` resets the card identically), so it
is safe whether or not a reader already had the original. A ``review`` is
never copied (the same device rating twice counts twice); it is logged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.eventlog import CAP_LIFT, NEW_CAP
from tutor.curriculum.ids import ulid, ulid_ms

if TYPE_CHECKING:
    from collections.abc import Iterable

COPYABLE: Final = frozenset({"taught", "untaught", CAP_LIFT, NEW_CAP})
_CONTENT: Final = ("k", "s", "c", "day", "n", "at")  # not dev, eid, session
_logger = logging.getLogger(__name__)


def _content(event: dict[str, Any]) -> tuple[object, ...]:
    return tuple(event.get(k) for k in _CONTENT)


def stranded(events: Iterable[dict[str, Any]], dev: str) -> list[dict[str, Any]]:
    """``dev``'s events stored after a higher own eid, with no copy above it."""
    own = [e for e in events if e["dev"] == dev]
    top: dict[tuple[object, ...], str] = {}
    for event in own:
        key = _content(event)
        top[key] = max(top.get(key, ""), event["eid"])
    out, newest = [], ""
    for event in own:
        if event["eid"] < newest and top[_content(event)] <= newest:
            out.append(event)
        newest = max(newest, event["eid"])
    return out


def copies(
    events: Iterable[dict[str, Any]], dev: str, now_ms: int
) -> list[dict[str, Any]]:
    """Fresh-eid copies of ``dev``'s stranded events, above every own eid."""
    events = list(events)
    todo = stranded(events, dev)
    if not todo:
        return []
    newest = max(e["eid"] for e in events if e["dev"] == dev)
    floor = max(now_ms, ulid_ms(newest) + 1)
    out = []
    for event in todo:
        if event["k"] not in COPYABLE:
            _logger.warning("stranded %s %s not re-minted", event["k"], event["eid"])
            continue
        out.append({**event, "eid": ulid(floor)})
    return out
