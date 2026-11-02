# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the ``mock`` kind (timed mock test; ``DOCS-contract-mock.md``).

One kind, ``op`` picks the action. RTDB drops empty strings and lists, so an
absent ``answer`` means "" and every field but ``op`` may be absent.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

OPS: Final = ("start", "answer", "run", "finish", "get")
DEFAULT_MINUTES: Final = 60
MIN_MINUTES: Final = 5
MAX_MINUTES: Final = 180
MAX_ANSWER: Final = 8000
_MOCK: Final = re.compile(r"[0-9a-f]{12}", re.ASCII)
_TASK: Final = re.compile(r"[a-z0-9_]{1,24}", re.ASCII)


def _op(value: object) -> str:
    if isinstance(value, str) and value in OPS:
        return value
    raise ValueError


def _mock_id(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and _MOCK.fullmatch(value):
        return value
    raise ValueError


def _task(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and _TASK.fullmatch(value):
        return value
    raise ValueError


def _minutes(value: object) -> int:
    if value is None:
        return DEFAULT_MINUTES
    if isinstance(value, int) and MIN_MINUTES <= value <= MAX_MINUTES:
        return int(value)
    raise ValueError


def _answer(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str) and len(value) <= MAX_ANSWER:
        return value
    raise ValueError


def _ts(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "mock": {
        "op": _op,
        "mock_id": _mock_id,
        "minutes": _minutes,
        "task": _task,
        "answer": _answer,
        "ts": _ts,
    },
}
