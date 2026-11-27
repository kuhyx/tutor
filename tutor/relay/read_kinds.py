# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``read_next`` / ``read_rate``: read mode over the relay (``tutor.read_mode``).

Never gated on Claude: read mode is what the app opens while Claude is out.
The rating's time is the learner's (``learner_time``), as for a drill pick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final
from weakref import WeakKeyDictionary

from tutor.read_mode import ReadMode
from tutor.relay.context import learner_time

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.engine import Engine
    from tutor.relay.context import RequestContext

_READS: Final[WeakKeyDictionary[Engine, ReadMode]] = WeakKeyDictionary()


def read_mode(engine: Engine) -> ReadMode:
    """The engine's read mode (its open prompt lives as long as this process)."""
    found = _READS.get(engine)
    if found is None:
        found = _READS[engine] = ReadMode(engine.store, engine.ctx)
    return found


async def read_next(ctx: RequestContext) -> dict[str, Any]:
    """The next untaught card to read (no model)."""
    return read_mode(ctx.engine).next(ctx.body["subject"], ctx.now())


async def read_rate(ctx: RequestContext) -> dict[str, Any]:
    """Rate the open card; its events and any credited minute are written."""
    body = ctx.body
    rated = str(body["prompt_id"]), str(body["rating"])
    return read_mode(ctx.engine).rate(*rated, learner_time(ctx))


HANDLERS: Final[dict[str, Callable[[RequestContext], Awaitable[dict[str, Any]]]]] = {
    "read_next": read_next,
    "read_rate": read_rate,
}
