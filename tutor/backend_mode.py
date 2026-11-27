# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Whether the running request drives a free-model session (``free_backend``).

A context variable, set by the relay around a free session's request and
inherited by the tasks it spawns (the model process), so code far from the
relay can tell without a parameter: a free session never records a Claude
outage window, never opens an unchecked card for a check (only Claude
checks) and marks each card it ends ``unchecked`` (spec Q9).
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Final

FREE: Final[ContextVar[bool]] = ContextVar("tutor_free_backend", default=False)


def free() -> bool:
    """Whether the current request runs on the free backend."""
    return FREE.get()
