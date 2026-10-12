# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The build lane's handlers (``tutor.curriculum.handlers``) and expected errors.

Curriculum handlers block (model calls, page fetches), so they run in a
worker thread on the engine's curriculum context. Their refusals are
``tutor.curriculum.errors.RequestError`` (a ``ValueError`` with ``.code``).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Final

from claude_agent_sdk import ClaudeSDKError

from tutor.curriculum import handlers as cur
from tutor.relay.errors import RequestError
from tutor.relay.rtdb import RtdbError

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

# What a handler may fail with; anything else is a bug that propagates (the
# lane logs it and the request is retried on the next rescan, up to gave_up).
BASE_ERRORS: Final = (
    RequestError,
    ClaudeSDKError,
    RtdbError,
    OSError,
    RuntimeError,
    ValueError,
    LookupError,
    TypeError,
    AttributeError,
    ArithmeticError,
)


async def build(ctx: RequestContext) -> dict[str, Any]:
    """Run the build-lane handler of ``ctx.request.kind`` in a thread."""
    handler = cur.BUILD_HANDLERS[ctx.request.kind]
    data: dict[str, Any] = await asyncio.to_thread(handler, ctx.body, ctx.engine.ctx)
    return data


def expected(err: BaseException) -> bool:
    """A failure to report as a result (ours, or anything with a contract ``code``)."""
    return isinstance(err, BASE_ERRORS) or isinstance(getattr(err, "code", None), str)
