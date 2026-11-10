# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What every request handler gets (chat lane here, build lane in curriculum).

A handler is ``async def handler(ctx: RequestContext) -> dict`` returning the
result ``data``, or raising ``RequestError(code, message)``. Handlers never
write ``requests/`` and never publish sessions themselves: the lane does
both, after the handler returned. ``ctx.touched`` names extra sessions the
handler changed (the live one before and after is always republished).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tutor.clock import activity_time

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.engine import Engine
    from tutor.relay.done import DoneMap
    from tutor.relay.phases import PhaseSink
    from tutor.relay.projection import Publisher
    from tutor.relay.protocol import Request
    from tutor.relay.rtdb import Rtdb


@dataclass
class RequestContext:
    """One request being served, and the worker's shared collaborators."""

    request: Request
    engine: Engine
    rtdb: Rtdb
    publisher: Publisher
    phase: Callable[[str], None]  # report a phase (mirrored to the claim)
    now: Callable[[], float]
    touched: set[str] = field(default_factory=set)

    @property
    def body(self) -> dict[str, Any]:
        """The validated request body (unknown fields already dropped)."""
        return self.request.body


def activity_ts(ctx: RequestContext) -> float:
    """When the answer in ``ctx`` was given: its ``sent_at``, clamped to now.

    The focus beat of an offline answer backs the time it was given, not the
    sync time (``clock.activity_time``).
    """
    sent = ctx.request.sent_at_ms
    return activity_time(ctx.now(), None if sent is None else sent / 1000)


@dataclass(frozen=True)
class Wiring:
    """The worker's long-lived collaborators, shared by every part of the relay."""

    rtdb: Rtdb
    engine: Engine
    publisher: Publisher
    done: DoneMap
    sink: PhaseSink
    worker: str  # this worker's device id
    now: Callable[[], float]
