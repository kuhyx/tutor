# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``card_edits``: the deck changes a tutor turn asks for (``tutor.edit_flow``).

Each entry is one op: ``edit`` (new front/back of ``card``, optionally a new
``source`` page with ``quote``), ``add`` (a new
card in ``topic`` from front, back and a ``source`` URL), ``remove``
(suspend ``card``), ``mnemonic`` (``text``: the card's memory aid, "" clears
it) or ``split`` (``card`` into the 2-4 drafts of ``into``;
``DOCS-contract-struggle.md``). An empty ``card`` means the target card, an
empty ``topic`` its topic. Read forgivingly: an entry without a known op is
dropped, but a split keeps every slot of ``into`` (a junk draft is empty, so
the split is refused whole rather than quietly made smaller).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

OPS: Final = ("edit", "add", "remove", "mnemonic", "split")
_STR: Final = {"type": "string"}
_FIELDS: Final = ("card", "topic", "front", "back", "source", "quote", "reason", "text")
_PART_FIELDS: Final = ("front", "back", "source", "quote")
PART_SCHEMA: Final = {
    "type": "object",
    "properties": dict.fromkeys(_PART_FIELDS, _STR),
    "required": list(_PART_FIELDS),
    "additionalProperties": False,
}
ITEM_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": list(OPS)},
        **dict.fromkeys(_FIELDS, _STR),
        "into": {"type": "array", "items": PART_SCHEMA},
    },
    "required": ["op", *_FIELDS, "into"],
    "additionalProperties": False,
}
DOC: Final = (
    "Usually []. One entry per change to the deck: op edit (card, front, "
    "back; optionally a new source URL and quote), add (topic, front, back, "
    "source URL, quote), remove (card), mnemonic (card, text: a memory aid of "
    "at most 40 words on one line, empty text clears it) or split (card, "
    "into: 2-4 smaller cards, each front, back, quote and a source URL, empty "
    "= the card's own source); "
    "`quote`: words of the page's supporting sentence, in the page's "
    "language (searched for, never copied); empty "
    "card = the target card, empty topic = its topic, an empty field keeps "
    "the old text; `text` and `into` are empty for the other ops. `reason`: "
    "why, in a few words."
)
SCHEMA: Final = {"type": "array", "description": DOC, "items": ITEM_SCHEMA}


@dataclass(frozen=True)
class SplitPart:
    """One card a ``split`` makes; empty strings mean "not given"."""

    front: str = ""
    back: str = ""
    source: str = ""
    quote: str = ""


@dataclass(frozen=True)
class CardEdit:
    """One requested change; empty strings mean "not given"."""

    op: str
    card: str = ""
    topic: str = ""
    front: str = ""
    back: str = ""
    source: str = ""
    quote: str = ""
    reason: str = ""
    text: str = ""
    into: tuple[SplitPart, ...] = ()


def _words(raw: dict[object, object], keys: tuple[str, ...]) -> dict[str, str]:
    return {k: " ".join(str(raw.get(k) or "").split()) for k in keys}


def _part(raw: object) -> SplitPart:
    return (
        SplitPart(**_words(raw, _PART_FIELDS)) if isinstance(raw, dict) else SplitPart()
    )


def _one(raw: object) -> CardEdit | None:
    if not isinstance(raw, dict) or raw.get("op") not in OPS:
        return None
    into = raw.get("into") if raw["op"] == "split" else None
    parts = tuple(_part(p) for p in into) if isinstance(into, list) else ()
    return CardEdit(str(raw["op"]), **_words(raw, _FIELDS), into=parts)


def parse(raw: object) -> tuple[CardEdit, ...]:
    """The well-formed entries of a turn's ``card_edits`` (absent: none)."""
    items = raw if isinstance(raw, list) else []
    return tuple(found for item in items if (found := _one(item)) is not None)
