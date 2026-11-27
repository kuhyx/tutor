# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the ``read_next`` / ``read_rate`` kinds (read mode)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from tutor.curriculum.ids import SLUG_CHARS, valid_eid
from tutor.read_mode import RATINGS

if TYPE_CHECKING:
    from collections.abc import Callable

# As ``protocol.SLUG`` / ``SLUG_MAX`` (importing them is a cycle).
_SLUG: Final = re.compile(rf"[{SLUG_CHARS}]+(-[{SLUG_CHARS}]+)*")
_SLUG_MAX: Final = 48


def _opt_slug(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and len(value) <= _SLUG_MAX and _SLUG.fullmatch(value):
        return value
    raise ValueError


def _ulid(value: object) -> str:
    if valid_eid(value):
        return str(value)
    raise ValueError


def _rating(value: object) -> str:
    if isinstance(value, str) and value in RATINGS:
        return value
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "read_next": {"subject": _opt_slug},
    "read_rate": {"prompt_id": _ulid, "rating": _rating},
}
