# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pieces of :func:`tutor.curriculum.eventlog.parse` that name no card.

``cap_lift`` / ``new_cap`` (the old daily cap) and ``subject_archive`` /
``subject_unarchive``; split out so ``eventlog.py`` stays under the
250-line gate. :class:`MalformedError` is what every parser raises.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any, Final

from tutor.curriculum.ids import valid_id

CAP_LIFT: Final = "cap_lift"  # {"day"}: old daily cap lift, kept, unused
CAP_MIN: Final = 1
CAP_MAX: Final = 200
DAY: Final = re.compile(r"\d{4}-\d{2}-\d{2}")


class MalformedError(ValueError):
    """An event that breaks the contract; ``parse`` logs why and drops it."""


def as_int(value: object) -> int | None:
    """``value`` if it is a real int (a bool is not)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _day(value: object) -> str:
    """``value`` if it is ``YYYY-MM-DD`` naming a real date."""
    msg = f"day {value!r}"
    if not isinstance(value, str) or not DAY.fullmatch(value):
        raise MalformedError(msg)
    try:
        date.fromisoformat(value)
    except ValueError as err:  # 2026-02-30: the shape is right, the date is not
        raise MalformedError(msg) from err
    return value


def global_event(raw: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """``cap_lift`` (``day``) / ``new_cap`` (``n`` in 1..200): no subject or card."""
    if head["k"] == CAP_LIFT:
        return {**head, "day": _day(raw.get("day"))}
    n = as_int(raw.get("n"))
    if n is None or not CAP_MIN <= n <= CAP_MAX:
        msg = f"n {raw.get('n')!r}"
        raise MalformedError(msg)
    return {**head, "n": n}


def subject_event(raw: dict[str, Any], head: dict[str, Any]) -> dict[str, Any]:
    """``subject_archive`` / ``subject_unarchive``: ``s`` only, no card."""
    if not valid_id(raw.get("s")):
        msg = "bad subject id"
        raise MalformedError(msg)
    return {**head, "s": raw["s"]}
