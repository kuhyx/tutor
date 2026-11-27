# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Which module a review minute belongs to (contract C1, ``DOCS-contract.md`` §7).

A review row's signed ``detail`` names ``subject``, the ``module`` of the card
whose review completed the minute (the event that sets ``ended_at``) and
``activity: "review"``. The module is the card's ``module`` in the subject's
``cards.json``; a card or subject that is gone leaves the row untagged (it
still pays tutor minutes), unless the subject is a GATED LeetCode one: then the
row names only its ``subject``, so it is written as LeetCode time
(``ledger_pay.kind_for``), never tutor time (kuhy, 2026-11-27).
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

from tutor.curriculum.eventlog import DRILL
from tutor.curriculum.theory_phase import GATED
from tutor.ledger_pay import Taught
from tutor.ledger_twin import REVIEW, TagFor

if TYPE_CHECKING:
    from collections.abc import Iterable

    from tutor.clock import BlockReady
    from tutor.curriculum.context import Context

# (subject slug, card id) -> the card's module id; None when it cannot be told.
Resolve = Callable[[str, str], str | None]
_logger = logging.getLogger(__name__)


def card_modules(ctx: Context) -> Resolve:
    """A resolver reading each subject's ``cards.json`` once (one credit pass)."""
    seen: dict[str, dict[str, str]] = {}

    def resolve(subject: str, card: str) -> str | None:
        if subject not in seen:
            try:
                found = ctx.subjects.cards(subject)
            except (OSError, ValueError, TypeError) as exc:  # bad id, bad file
                _logger.warning("cards of %s unreadable: %s", subject, exc)
                found = {}
            seen[subject] = {cid: rec.module for cid, rec in found.items()}
        return seen[subject].get(card) or None

    return resolve


def taught_by(event: dict[str, Any], resolve: Resolve | None) -> Taught | None:
    """The tags of the review ``event``'s card; ``None`` when it cannot be told."""
    subject, card = event.get("s"), event.get("c")
    if resolve is None or not isinstance(subject, str) or not isinstance(card, str):
        return None
    module = resolve(subject, card)
    if module is not None:
        return Taught(subject=subject, module=module, activity=REVIEW)
    # No module the guard could count, but still never tutor time.
    return Taught(subject=subject, activity=REVIEW) if subject in GATED else None


def by_unit(
    done: Iterable[tuple[BlockReady, dict[str, Any]]],
    sid: str,
    resolve: Resolve | None,
) -> Callable[[BlockReady], Taught | None]:
    """``credit_units(taught_of=)`` for one session: the unit's completing review."""
    events = {unit.block: event for unit, event in done}

    def taught_of(unit: BlockReady) -> Taught | None:
        event = events[unit.block]
        found = taught_by(event, resolve)
        if found is None:
            _logger.warning(
                "app review: %s-m%d row untagged, no module for card %s of %s",
                sid,
                unit.block,
                event.get("c"),
                event.get("s"),
            )
        return found

    return taught_of


def tag_for(
    sessions: dict[str, list[tuple[BlockReady, dict[str, Any]]]],
    drills: Iterable[dict[str, Any]],
    day: str,
    resolve: Resolve | None,
) -> TagFor:
    """The backfill's question for local ``day`` (``YYYYMMDD``): what a row carries.

    App-review rows (``review-<day>-<dev>-m<n>``) take the tags of the review
    that completed minute ``n``, if the row ended at that review. PC-drill
    rows (``drill-<day>-...``) end at their answer's ``at``, so they take the
    tags of the drill review answered at that millisecond. Anything else (a
    lesson, Anki, leftover, carry, another day): ``None``.
    """
    wanted: dict[str, tuple[float, dict[str, Any]]] = {
        f"{sid}-m{unit.block}": (unit.ended_at, event)
        for sid, done in sessions.items()
        if sid.startswith(f"review-{day}-")
        for unit, event in done
    }
    answered = {e["at"]: e for e in drills if e.get("src") == DRILL}

    def question(entry: str, ended: float) -> Taught | None:
        if entry.startswith(f"drill-{day}-"):
            event = answered.get(int(ended * 1000))
        else:
            found = wanted.get(entry)
            event = found[1] if found and found[0] == ended else None
        return taught_by(event, resolve) if event else None

    return question
