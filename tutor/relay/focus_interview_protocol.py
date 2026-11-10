# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the interview kinds (``DOCS-contract-focus.md``, Interview).

Shape checks only. Which milestone takes which evidence, the trip ratchet and
the date rules are ``focus_project``'s and come back as ``focus_refused``.
"""

from __future__ import annotations

from datetime import datetime
import math
import re
from typing import TYPE_CHECKING, Final

from tutor.relay.focus_protocol import _choice, _day, _slug, _work_url

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_TRIPS: Final = 20
MAX_CHUNKS: Final = 16
MILESTONE: Final = re.compile(r"[a-z_]{2,16}(:\d{4}-\d{2}-\d{2})?", re.ASCII)
SHA256: Final = re.compile(r"[0-9a-f]{64}", re.ASCII)
ULID: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}", re.ASCII)
MIMES: Final = ("image/png", "image/jpeg", "image/webp")
KINDS: Final = ("file", "tap", "score", "slot", "slot_confirm")
MAX_VALUE: Final = 40


def _kind(value: object) -> str:
    return "focus" if value is None else _choice("focus", "interview")(value)


def _test_at(value: object) -> str | None:
    """A naive local ``YYYY-MM-DDTHH:MM[:SS]``; absent = ``None``."""
    if value is None:
        return None
    if (
        isinstance(value, str)
        and len(value) in {16, 19}
        and "T" in value
        and datetime.fromisoformat(value).tzinfo is None
    ):
        return value
    raise ValueError


def _invite(value: object) -> str:
    return _work_url(value) or ""


def _trips(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_TRIPS:
        raise ValueError
    out = []
    for row in value:
        given = row if isinstance(row, dict) else {}
        start, end = _day(given.get("start")), _day(given.get("end"))
        if end < start:  # ISO dates compare as text
            raise ValueError
        out.append({"start": start, "end": end})
    return out


def _flag(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return bool(value)
    raise ValueError


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError


def _milestone(value: object) -> str:
    if isinstance(value, str) and MILESTONE.fullmatch(value):
        return value
    raise ValueError


def _value(value: object) -> object:
    """A tap (absent / ``true``), a score, or a short text (the slot datetime)."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float) and math.isfinite(value):
        return value
    if isinstance(value, str) and len(value) <= MAX_VALUE:
        return value
    raise ValueError


def _upload(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and ULID.fullmatch(value):
        return value
    raise ValueError


def _chunks(value: object) -> int | None:
    if value is None:
        return None
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_CHUNKS
    ):
        return value
    raise ValueError


def _sha(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and SHA256.fullmatch(value):
        return value
    raise ValueError


def _mime(value: object) -> str | None:
    return None if value is None else _choice(*MIMES)(value)


CREATE_EXTRA: Final[dict[str, Callable[[object], object]]] = {
    "kind": _kind,
    "test_at": _test_at,
    "invite_url": _invite,
    "trips": _trips,
    "no_trip": _flag,
}

FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "focus_evidence": {
        "id": _slug,
        "milestone": _milestone,
        "kind": _choice(*KINDS),
        "value": _value,
        # ``file`` only: chunks of the image in ``uploads/{upload}`` (never inline).
        "upload": _upload,
        "chunks": _chunks,
        "sha256": _sha,
        "mime": _mime,
    },
    "focus_trip": {"id": _slug, "start": _day, "end": _day},
    "focus_weekend": {"id": _slug, "saturday": _day, "trip": _bool},
}
