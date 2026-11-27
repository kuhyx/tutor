# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Claude's check of a card taught without it (``README.md`` "Fallback").

``SubjectSource.pick`` opens an unchecked card (``curriculum.check_marks``)
before any new one. Its session gets :func:`section` in the system prompt:
one check question first, no teaching. When the tutor ends the card
(``card_done``), :func:`finish` reads the session's FIRST graded check:

* passed: a ``checked`` event; the card keeps its FSRS state (no re-teach);
* not passed (or never graded): the tutor taught it in full, so the card is
  taught again, rated Again right after (it comes back in a day), and
  ``checked``.

A card a free-model chat finishes is taught and marked ``unchecked``
(``src: free``), like read mode (spec Q9).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from tutor import backend_mode
from tutor.curriculum.eventlog import (
    CHECKED,
    FREE,
    review_event,
    unchecked_event,
    worker_event,
)
from tutor.curriculum.source import SubjectSource

if TYPE_CHECKING:
    from tutor.curriculum.source import CardSource

AGAIN: Final = 1
SECTION: Final = (
    "# This card was covered without a tutor\n"
    "The learner read this card (or a weaker model taught it) while you were "
    "unavailable. It counts as taught but is unchecked. Do NOT teach it first: "
    "on your first turn pose ONE check question on the target card's answer, "
    "in `check`, with a one-line greeting. If the learner passes, confirm in "
    "a sentence and end the card (card_done) without re-teaching. If not, "
    "teach the card in full as usual, then end it.\n\n"
)


def unchecked(src: CardSource, card_id: str) -> bool:
    """Whether ``card_id`` of ``src`` waits for Claude's check (never in free)."""
    if backend_mode.free() or not isinstance(src, SubjectSource):
        return False
    return src.ctx.fold().card(src.subject, card_id).unchecked


def section(src: CardSource, card_id: str) -> str:
    """The system prompt's check section for ``card_id`` (empty if checked)."""
    return SECTION if unchecked(src, card_id) else ""


def first_grade(src: SubjectSource, session: str, turn: dict[str, Any]) -> bool:
    """Whether the session's first graded check passed (``turn``: the current)."""
    path = src.store.root / "sessions" / f"{session}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    logged = (json.loads(line) for line in lines if line.strip())
    turns = [e["turn"] for e in logged if e.get("type") == "tutor" and "turn" in e]
    for found in [*turns, turn]:
        result = found.get("check_result")
        if result is not None:
            return bool(result.get("passed"))
    return False


def finish(src: CardSource, card_id: str, session: str, turn: dict[str, Any]) -> None:
    """The tutor ended ``card_id``: taught, checked or re-taught (module doc)."""
    if not isinstance(src, SubjectSource):
        src.mark(card_id, session, done=True)
        return
    ref, dev = (src.subject, card_id), src.ctx.device
    if unchecked(src, card_id) and first_grade(src, session, turn):
        at = src.ctx.clock()
        src.ctx.log.append([worker_event(CHECKED, ref, dev=dev, at=at)])
        return
    was_unchecked = unchecked(src, card_id)
    src.mark(card_id, session, done=True)
    at = src.ctx.clock() + 1  # strictly after the taught: the fold sorts by at
    if was_unchecked:
        rev = src.ctx.subjects.cards(src.subject)[card_id].rev
        again = review_event(ref, AGAIN, dev=dev, span=(at, at), rev=rev)
        checked = worker_event(CHECKED, ref, dev=dev, at=at + 1)
        src.ctx.log.append([again, checked])
    elif backend_mode.free():
        src.ctx.log.append([unchecked_event(ref, dev=dev, at=at, src=FREE)])
