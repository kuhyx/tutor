# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request fields of the ``plan_today`` / ``plan_step_done`` kinds."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

_STEP: Final = re.compile(r"[a-z0-9_-]{1,32}", re.ASCII)


def _step_id(value: object) -> str:
    if isinstance(value, str) and _STEP.fullmatch(value):
        return value
    raise ValueError


FIELDS: Final[dict[str, dict[str, Callable[[object], object]]]] = {
    "plan_today": {},
    "plan_step_done": {"id": _step_id},
}
