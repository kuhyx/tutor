# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of ``rework_open`` / ``rework_turn`` (``DOCS-contract-coach.md``).

Shape checks only; whether the subject and module exist is the handler's.
The id field is ``rework_id``, never ``session``: the relay mirrors a body's
``session`` into ``sessions/<id>/meta``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from tutor.curriculum.ids import valid_id
from tutor.relay.lc_protocol import MAX_TEXT

if TYPE_CHECKING:
    from collections.abc import Callable

# A LeetCode titleSlug: it names a file of the guard's, so never ``../x``.
_SLUG: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
MAX_SLUG: Final = 120
_REWORK_ID: Final = re.compile(r"[0-9a-f]{12}", re.ASCII)


def _id(value: object) -> str:
    if valid_id(value):
        return str(value)
    raise ValueError


def _slug(value: object) -> str:
    if isinstance(value, str) and len(value) <= MAX_SLUG and _SLUG.fullmatch(value):
        return value
    raise ValueError


def _rework_id(value: object) -> str:
    if isinstance(value, str) and _REWORK_ID.fullmatch(value):
        return value
    raise ValueError


def _text(value: object) -> str:
    if isinstance(value, str) and value.strip() and len(value) <= MAX_TEXT:
        return value
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "rework_open": {"subject": _id, "module": _id, "slug": _slug},
    "rework_turn": {"rework_id": _rework_id, "text": _text},
}
