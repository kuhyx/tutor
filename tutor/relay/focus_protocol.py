# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the ``focus_*`` kinds (``DOCS-contract-focus.md``).

Shape checks only; the rules (overlap, unlock <= daily, end >= start) are
``focus_project``'s and come back as ``focus_refused``. RTDB drops empty
lists, so an absent list field means ``[]``.
"""

from __future__ import annotations

from datetime import date
import re
from typing import TYPE_CHECKING, Final

from tutor.curriculum.ids import SLUG_CHARS

if TYPE_CHECKING:
    from collections.abc import Callable

_DAY: Final = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_HOST: Final = re.compile(r"[A-Za-z0-9*._-]+", re.ASCII)
_SLUG: Final = re.compile(rf"[{SLUG_CHARS}]+(-[{SLUG_CHARS}]+)*")
GATES: Final = frozenset({"leetcode", "reading", "tutor"})  # what fp can replace
MAX_NAME: Final = 80
MAX_MINUTES: Final = 720
MAX_LIST: Final = 48
MAX_PATTERNS: Final = 20
MAX_PATTERN: Final = 100
MAX_SLUG: Final = 48


def _slug(value: object) -> str:
    if isinstance(value, str) and len(value) <= MAX_SLUG and _SLUG.fullmatch(value):
        return value
    raise ValueError


def _name(value: object) -> str:
    if isinstance(value, str) and value.strip() and len(value) <= MAX_NAME:
        return value
    raise ValueError


def _day(value: object) -> str:
    """``YYYY-MM-DD`` naming a real date."""
    if isinstance(value, str) and _DAY.fullmatch(value):
        date.fromisoformat(value)  # ValueError for 2027-02-30
        return value
    raise ValueError


def _opt_day(value: object) -> str | None:
    return None if value is None else _day(value)


def _ms(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ValueError


def _choice(*allowed: str) -> Callable[[object], str]:
    def check(value: object) -> str:
        if isinstance(value, str) and value in allowed:
            return value
        raise ValueError

    return check


def _minutes(low: int) -> Callable[[object], int]:
    def check(value: object) -> int:
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and low <= value <= MAX_MINUTES
        ):
            return value
        raise ValueError

    return check


def _gates(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and all(v in GATES for v in value):
        return [str(v) for v in value]
    raise ValueError


def _subjects(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and len(value) <= MAX_LIST:
        return [_slug(v) for v in value]
    raise ValueError


def _patterns(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and len(value) <= MAX_PATTERNS:
        for item in value:
            ok = isinstance(item, str) and len(item) <= MAX_PATTERN
            if not (ok and _HOST.fullmatch(str(item))):
                raise ValueError
        return [str(v) for v in value]
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "focus_status": {},
    "focus_event": {
        "event": _choice("start", "checkin", "stop"),
        "ts": _ms,  # the client's tap time, unix ms (clamped by the handler)
        "platform": _choice("phone", "pc"),
    },
    "focus_create": {
        "name": _name,
        "start": _day,
        "end": _day,
        "replaces": _gates,
        "daily_minutes": _minutes(1),
        "unlock_minutes": _minutes(0),
        "subjects": _subjects,
        "site_patterns": _patterns,
    },
    "focus_end": {"id": _slug, "day": _opt_day},
}
