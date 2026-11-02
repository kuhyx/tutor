# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Late import of the optional coach libraries (a missing one is ``worker_error``)."""

from __future__ import annotations

import importlib
import importlib.util
from typing import TYPE_CHECKING

from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from types import ModuleType


def lib(name: str) -> ModuleType:
    """Import ``name``, or ``worker_error`` when its package is missing."""
    if importlib.util.find_spec(name.split(".", maxsplit=1)[0]) is None:
        msg = f"{name.split('.', maxsplit=1)[0]} is not installed on the worker"
        raise RequestError(msg, code="worker_error")
    return importlib.import_module(name)
