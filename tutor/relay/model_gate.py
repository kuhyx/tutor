# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The up-front refusal of a session kind while no model at all can answer.

Claude out (a recorded outage window) is not enough: the local model then
answers the session (``tutor.local_session``). Only when Ollama is down too
is the kind refused before its handler runs, so a failed ``next`` keeps the
live session and the app opens the drill.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tutor import local_model, outage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.relay.context import RequestContext

_logger = logging.getLogger(__name__)


def needs_a_model(
    handler: Callable[[RequestContext], Awaitable[dict[str, Any]]],
) -> Callable[[RequestContext], Awaitable[dict[str, Any]]]:
    """``handler``, refused up front while neither Claude nor Ollama can answer.

    Refused before the handler runs, so a failed ``next`` keeps the session.
    """

    async def gated(ctx: RequestContext) -> dict[str, Any]:
        try:
            outage.ensure_available(ctx.now())
        except outage.ClaudeUnavailableError as err:
            if not await asyncio.to_thread(local_model.ready):
                raise
            _logger.warning("%s; the local model answers %s", err, ctx.request.kind)
        return await handler(ctx)

    return gated
