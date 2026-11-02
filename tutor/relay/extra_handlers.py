# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Chat-lane handlers of the kinds that live outside ``chat.py``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tutor.relay.mock import mock_request
from tutor.relay.plan import plan_step_done, plan_today

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.relay.context import RequestContext

HANDLERS: Final[dict[str, Callable[[RequestContext], Awaitable[dict[str, Any]]]]] = {
    "mock": mock_request,
    "plan_today": plan_today,
    "plan_step_done": plan_step_done,
}
