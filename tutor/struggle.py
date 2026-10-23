# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Help on a struggling card: ``session_start`` ``struggle: true``.

``DOCS-contract-struggle.md`` §5. The card must be taught (a re-teach, so it
is exempt from the daily new cap); its ``struggle(c)`` (fold step 7) and its
last 10 reviews go into the tutor's system prompt with rule 16
(``struggle_rules``). The transcript's ``start`` event carries ``"struggle":
true``, so a resumed session gets the same prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.source import SubjectSource

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.source import CardSource

LAST_REVIEWS: Final = 10
RATINGS: Final = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


@dataclass(frozen=True)
class Brief:
    """What the tutor is told: the Again run and the last reviews ``(at, r)``."""

    count: int
    reviews: tuple[tuple[int, int], ...]


def _gather(src: SubjectSource, card_id: str) -> Brief:
    state = src.ctx.fold().card(src.subject, card_id)
    found = src.ctx.subjects.cards(src.subject).get(card_id)
    count = state.struggle(found.rev) if found is not None else 0
    return Brief(count, tuple(state.reviews[-LAST_REVIEWS:]))


def brief(src: CardSource, card_id: str) -> Brief:
    """The brief for ``card_id``; ``bad_request`` unless a taught curriculum card."""
    if not isinstance(src, SubjectSource):
        msg = "help on a struggling card needs a curriculum subject"
        raise RequestError(BAD_REQUEST, msg)
    if not src.ctx.fold().card(src.subject, card_id).taught:
        msg = f"{card_id} is not taught yet: help is for a card already learned"
        raise RequestError(BAD_REQUEST, msg)
    return _gather(src, card_id)


def tag(found: Brief | None) -> dict[str, Any]:
    """The ``start`` event's mark of a struggle session (else nothing)."""
    return {"struggle": True} if found is not None else {}


def resumed(src: CardSource, card_id: str, path: Path) -> Brief | None:
    """The brief again when ``path`` started in struggle mode (else None)."""
    with path.open(encoding="utf-8") as handle:
        first = json.loads(handle.readline() or "{}")
    if not first.get("struggle") or not isinstance(src, SubjectSource):
        return None
    return _gather(src, card_id)  # re-taught since: a run of 0, still help


def when(at_ms: int) -> str:
    """A review time as the PC-local ``YYYY-MM-DD HH:MM``."""
    return (
        datetime.fromtimestamp(at_ms / 1000, tz=UTC)
        .astimezone()
        .strftime("%Y-%m-%d %H:%M")
    )


def section(found: Brief) -> str:
    """The system prompt's ``# Struggling card`` block (rule 16)."""
    lines = "".join(f"- {when(at)}: {RATINGS[r]}\n" for at, r in found.reviews)
    return (
        "# Struggling card\n"
        f"The learner rated Again {found.count} times in a row on this card in "
        "review (rule 16). Its last reviews, oldest first:\n"
        f"{lines or '(none)\n'}\n"
    )
