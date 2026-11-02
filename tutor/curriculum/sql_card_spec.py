# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One reviewable SQL card: its source, its example and how its back is made.

``front`` and ``rule`` are written by hand; the *result* in the back is the
real output of ``query`` on ``schema`` (a MySQL run, never typed in), so a
card cannot claim a result the engine does not give.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Outcome:
    """What the engine returned for one query: rows of text, or an error code."""

    ok: bool
    rows: tuple[tuple[str, ...], ...] = ()
    code: int | None = None


@dataclass(frozen=True)
class CardSpec:
    """A card; ``query`` empty means a rule-only card (no result in the back)."""

    key: str  # the card id is ``sql-<key>``
    front: str
    rule: str
    source: str
    excerpt: str
    schema: str = ""
    query: str = ""

    @property
    def card_id(self) -> str:
        """The stable card id."""
        return f"sql-{self.key}"


def render(outcome: Outcome) -> str:
    """The engine's answer as one short sentence-like string."""
    if not outcome.ok:
        return f"ERROR {outcome.code}."
    if not outcome.rows:
        return "No rows."
    if all(len(row) == 1 for row in outcome.rows):
        return ", ".join(row[0] for row in outcome.rows) + "."
    return " ".join("(" + ",".join(row) + ")" for row in outcome.rows) + "."


def back_text(spec: CardSpec, outcome: Outcome | None) -> str:
    """The card's back: the real result (if any), then the one-line rule."""
    if not spec.query:
        return spec.rule
    if outcome is None:
        msg = f"{spec.key} needs an engine result"
        raise ValueError(msg)
    return f"{render(outcome)} {spec.rule}"
