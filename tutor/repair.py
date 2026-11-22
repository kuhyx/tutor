# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One-off repair: cards the tutor finished while a gate dropped the result.

Until 2026-10-10 the engine ignored a tutor ``card_done`` unless a check had
passed (session ``20261010-153545-b193``: the card was never recorded done and
"next unfinished card" served it again). The transcripts still hold the
tutor's word, so this marks those cards done from them, by code. It runs once
per data dir (``Store.mark_repaired``): after that the manual override
(the ``card_done`` request) owns the state, and a restart must not undo it.

The second repair, :func:`unrefuse_done_cards` (2026-11-22), re-applies a
``card_done`` the engine refused for a prerequisite that the shared rule
(``gating.missing``, faa43ba) no longer demands.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import phase_gate
from tutor.curriculum.errors import RequestError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from tutor.curriculum.source import CardSource
    from tutor.store import Store

_logger = logging.getLogger(__name__)
NAME: Final = "tutor-card-done-v1"
UNREFUSE: Final = "tutor-unrefuse-v1"


def _tutor_done(path: Path) -> list[str]:
    """Card ids a tutor turn of this transcript finished, in order."""
    card, found = "", []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            # A line cut short by a kill: skip it, the rest still counts.
            _logger.warning("repair: unreadable line in %s skipped: %s", path.name, exc)
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") in {"start", "next_card"}:
            card = str(event.get("card", ""))
        elif event.get("type") == "tutor" and (event.get("turn") or {}).get(
            "card_done"
        ):
            found.append(card)
    return found


def repair_done_cards(store: Store) -> list[tuple[str, str]]:
    """Mark every tutor-finished card that is not done yet; ``[(card, session)]``."""
    if store.repaired(NAME):
        return []
    marked: list[tuple[str, str]] = []
    for path in sorted((store.root / "sessions").glob("*.jsonl")):
        for card in _tutor_done(path):
            if card and card not in store.progress()["cards_done"]:
                store.finish_card(card, path.stem)
                marked.append((card, path.stem))
                _logger.info("repair: marked %s done from session %s", card, path.stem)
    store.mark_repaired(NAME)
    return marked


def _events(path: Path) -> Iterator[dict[str, Any]]:
    """The readable events of one transcript, in order."""
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            _logger.warning(
                "unrefuse: unreadable line in %s skipped: %s", path.name, exc
            )
            continue
        if isinstance(event, dict):
            yield event


def _scan(root: Path) -> tuple[list[tuple[str, str, str, str]], dict[str, str]]:
    """``([(session, subject, card, at)], {card: when it was last set by hand})``.

    The first list holds every tutor turn whose ``card_done`` was refused, in
    transcript order; ``at`` is its ``logged_at``. The dict reads every
    ``card_done_manual`` of every transcript: a learner's choice made after a
    refusal is theirs, whichever way it went.
    """
    refused: list[tuple[str, str, str, str]] = []
    manual: dict[str, str] = {}
    for path in sorted((root / "sessions").glob("*.jsonl")):
        card, subject = "", ""
        for event in _events(path):
            kind, at = event.get("type"), str(event.get("logged_at", ""))
            if kind == "start":
                subject = str(event.get("subject") or "")
            if kind in {"start", "next_card"}:
                card = str(event.get("card", ""))
            elif kind == "card_done_manual":
                card_id = str(event.get("card", ""))
                manual[card_id] = max(manual.get(card_id, ""), at)
            elif kind == "tutor" and (event.get("turn") or {}).get("card_done_refused"):
                refused.append((path.stem, subject, card, at))
    return refused, manual


def _apply_one(
    store: Store,
    source_of: Callable[[str | None], CardSource],
    found: tuple[str, str, str, str],
) -> bool:
    """Re-apply one refused done if the current gate allows it; ``True``: flipped."""
    sid, subject, card_id, _ = found
    try:
        src = source_of(subject or None)
    except RequestError as err:
        _logger.warning("unrefuse: %s: %s; skipped", sid, err)
        return False
    card = next((c for c in src.cards() if c.id == card_id), None)
    if card is None:
        _logger.warning(
            "unrefuse: %s: card %r is not in the deck; skipped", sid, card_id
        )
        return False
    if card_id in src.done() or phase_gate.blockers(src, card):
        return False  # done since, or the gate still refuses it
    try:
        src.mark(card_id, sid, done=True)  # the same writer an accepted done uses
    except (ValueError, RequestError) as err:
        _logger.warning("unrefuse: %s: %s not marked: %s", sid, card_id, err)
        return False
    # What resume already replays for a manual done: the page shows the card
    # done and offers the next one. Never a credit row (``set_card_done``).
    store.log(sid, {"type": "card_done_manual", "card": card_id, "done": True})
    _logger.info("repair: marked %s done from session %s (was refused)", card_id, sid)
    return True


def unrefuse_done_cards(
    store: Store, source_of: Callable[[str | None], CardSource]
) -> list[tuple[str, str]]:
    """Re-apply the ``card_done`` the old gate refused; ``[(card, session)]``.

    Until faa43ba a card whose prerequisite sat in a module C3 refuses could
    never be marked done: the tutor said "Passed" and the engine logged
    ``card_done_refused``. For each such turn whose card is not done and which
    the CURRENT gate (``phase_gate.blockers``, as ``Engine._apply`` asks) no
    longer blocks, the card is marked through ``source.mark`` and the
    transcript gets a ``card_done_manual`` event. A card set by hand since
    the refusal is left alone. Once per data dir (``Store.mark_repaired``).
    """
    if store.repaired(UNREFUSE):
        return []
    refused, manual = _scan(store.root)
    flipped: list[tuple[str, str]] = []
    for found in refused:
        sid, _, card_id, at = found
        by_hand = manual.get(card_id)
        if by_hand is not None and by_hand >= at:
            continue  # the learner decided after the refusal
        if _apply_one(store, source_of, found):
            flipped.append((card_id, sid))
    store.mark_repaired(UNREFUSE)
    return flipped
