# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Chat-lane handlers of the kinds that live outside ``chat.py`` (none gated)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tutor.relay.focus_interview import focus_evidence, focus_trip, focus_weekend
from tutor.relay.mock import mock_request
from tutor.relay.plan import plan_step_done, plan_today
from tutor.relay.read_kinds import HANDLERS as READ_HANDLERS
from tutor.relay.rework import rework_open, rework_turn

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.relay.context import RequestContext

HANDLERS: Final[dict[str, Callable[[RequestContext], Awaitable[dict[str, Any]]]]] = {
    "focus_evidence": focus_evidence,
    "focus_trip": focus_trip,
    "focus_weekend": focus_weekend,
    "mock": mock_request,
    "plan_today": plan_today,
    "plan_step_done": plan_step_done,
    "rework_open": rework_open,
    "rework_turn": rework_turn,
    **READ_HANDLERS,
}
