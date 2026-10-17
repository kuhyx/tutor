# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``card_edits``: the deck changes a tutor turn asks for (``tutor.edit_flow``).

Each entry is one op: ``edit`` (new front/back of ``card``), ``add`` (a new
card in ``topic`` from front, back and a ``source`` URL) or ``remove``
(suspend ``card``). An empty ``card`` means the target card, an empty
``topic`` its topic. Read forgivingly: an entry without a known op is dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

OPS: Final = ("edit", "add", "remove")
_STR: Final = {"type": "string"}
_FIELDS: Final = ("card", "topic", "front", "back", "source", "reason")
ITEM_SCHEMA: Final = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": list(OPS)},
        **dict.fromkeys(_FIELDS, _STR),
    },
    "required": ["op", *_FIELDS],
    "additionalProperties": False,
}
DOC: Final = (
    "Usually []. One entry per change to the deck: op edit (card, front, "
    "back), add (topic, front, back, source URL) or remove (card); empty "
    "card = the target card, empty topic = its topic, an empty field keeps "
    "the old text. `reason`: why, in a few words."
)
SCHEMA: Final = {"type": "array", "description": DOC, "items": ITEM_SCHEMA}


@dataclass(frozen=True)
class CardEdit:
    """One requested change; empty strings mean "not given"."""

    op: str
    card: str = ""
    topic: str = ""
    front: str = ""
    back: str = ""
    source: str = ""
    reason: str = ""


def _one(raw: object) -> CardEdit | None:
    if not isinstance(raw, dict) or raw.get("op") not in OPS:
        return None
    given = {k: " ".join(str(raw.get(k) or "").split()) for k in _FIELDS}
    return CardEdit(str(raw["op"]), **given)


def parse(raw: object) -> tuple[CardEdit, ...]:
    """The well-formed entries of a turn's ``card_edits`` (absent: none)."""
    items = raw if isinstance(raw, list) else []
    return tuple(found for item in items if (found := _one(item)) is not None)
