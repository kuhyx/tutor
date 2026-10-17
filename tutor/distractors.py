# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The drill's wrong options: the other cards closest to the right one.

A topic is too broad to make a good distractor on its own: the automation
deck's 25 ``fundamentals`` cards share one, so "why replace relay panels?"
was offered watchdog and task-timing backs and the answer was obvious
(kuhy, 2026-10-15). Candidates are ranked by word overlap (Jaccard over
content words of front + back) with the right card, then same topic first,
then a hash order fixed by the prompt id. No model, so it works while Claude
is out.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Final

from tutor.curriculum.ids import tokenize

if TYPE_CHECKING:
    from tutor.cards import Card

OPTIONS: Final = 4
_MIN_LEN: Final = 4  # drops "the", "and", "a", "is" without a long stoplist
_STOP: Final = frozenset({
    "what", "which", "when", "where", "does", "that", "this", "with", "from",
    "into", "each", "they", "them", "their", "than", "then", "only", "also",
    "more", "most", "your", "have", "been", "were", "will", "would", "should",
})  # fmt: skip


def _words(card: Card) -> frozenset[str]:
    text = f"{card.front} {card.back}".lower()
    return frozenset(w for w in tokenize(text) if len(w) >= _MIN_LEN and w not in _STOP)


def _overlap(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _hash(seed: str, text: str) -> bytes:
    return hashlib.sha256(f"{seed}\0{text}".encode()).digest()


def mixed(seed: str, items: list[str]) -> list[str]:
    """``items`` in an order fixed by ``seed`` (a hash order, not a secret)."""
    return sorted(items, key=lambda s: _hash(seed, s))


def options_for(card: Card, pool: list[Card], seed: str) -> tuple[list[str], int]:
    """``card.back`` plus up to 3 distinct other backs, closest first, mixed."""
    mine = _words(card)
    others = [c for c in pool if c.id != card.id and c.back != card.back]
    ranked = sorted(
        others,
        key=lambda c: (
            -_overlap(mine, _words(c)),
            c.topic != card.topic,
            _hash(seed, c.back),
        ),
    )
    chosen = list(dict.fromkeys(c.back for c in ranked))[: OPTIONS - 1]
    shown = mixed(seed, [card.back, *chosen])
    return shown, shown.index(card.back)
