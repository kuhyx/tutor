# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The free-model chat: a tutor session on OmniRoute's ``free-best`` chain.

kuhy's fallback while Claude is out (spec Q8/Q9, ``README.md`` "Fallback"):
a glyph on the outage banner sends ``session_start`` with ``free: true``. The
session is the usual one (same prompt, tools and sandbox), but its CLI talks
to the local OmniRoute gateway (Anthropic API, ``free-best``) instead of
Claude: :func:`free_options.applied` sets the env the way ``claude-free`` does, and the
sandbox forwards that one loopback port (``TUTOR_MODEL_GATEWAY_PORT``).

:func:`gate` wraps every Claude chat kind (``relay.chat``). A request on a
free session (``session_start`` with ``free``, or any later request of the
session it started; a ``session_start`` without ``free`` ends that, so the
module gate's check of unchecked cards runs on Claude) skips the Claude
outage check, runs with
``backend_mode.FREE`` set, and turns a gateway failure into
``free_unavailable``; any other request goes through
``relay.model_gate.needs_a_model`` (Claude, else the local model).
:func:`marks` wraps the kinds that need no model but must know a free
session (``card_done``: its card is marked unchecked). Read mode
never needs any of this, so a gateway outage cannot block it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final
from weakref import WeakKeyDictionary

import httpx

from tutor import backend_mode, outage
from tutor.free_options import gateway, key
from tutor.relay.errors import RequestError
from tutor.relay.model_gate import needs_a_model

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.engine import Engine
    from tutor.relay.context import RequestContext

CODE: Final = "free_unavailable"
PROBE_TIMEOUT_S: Final = 3.0
_LIVE: Final[WeakKeyDictionary[Engine, str]] = WeakKeyDictionary()
# The probe's transport: None is the network; tests put a mock here.
PROBE_TRANSPORT: httpx.AsyncBaseTransport | None = None


def _down(why: str) -> RequestError:
    return RequestError(f"the free-model gateway is down: {why}", code=CODE, retry=True)


async def ensure_up() -> None:
    """Raise ``free_unavailable`` unless the gateway lists its models."""
    token = key()
    if not token:
        why = "no OmniRoute API key"
        raise _down(why)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(
            timeout=PROBE_TIMEOUT_S, transport=PROBE_TRANSPORT
        ) as client:
            reply = await client.get(f"{gateway()}/v1/models", headers=headers)
    except httpx.HTTPError as err:
        raise _down(type(err).__name__) from err
    if reply.status_code != httpx.codes.OK:
        why = f"HTTP {reply.status_code}"
        raise _down(why)


def live(engine: Engine) -> bool:
    """Whether ``engine``'s live session was started on the free backend."""
    sid = engine.session_id
    return bool(sid) and _LIVE.get(engine) == sid


def gate(
    handler: Callable[[RequestContext], Awaitable[dict[str, Any]]],
) -> Callable[[RequestContext], Awaitable[dict[str, Any]]]:
    """``handler`` on the right backend (module docstring)."""
    other = needs_a_model(handler)  # Claude, else the local model, else refused

    async def gated(ctx: RequestContext) -> dict[str, Any]:
        starting = bool(ctx.body.get("free"))
        if not starting and ctx.request.kind == "session_start":
            _LIVE.pop(ctx.engine, None)  # a start without ``free`` is Claude's
        if not starting and not live(ctx.engine):
            return await other(ctx)
        if starting:
            await ensure_up()
        token = backend_mode.FREE.set(True)
        try:
            result = await handler(ctx)
        except outage.ClaudeUnavailableError as err:
            raise _down(err.reason) from None
        finally:
            backend_mode.FREE.reset(token)
        _LIVE[ctx.engine] = ctx.engine.session_id
        return result

    return gated


def marks(
    handler: Callable[[RequestContext], Awaitable[dict[str, Any]]],
) -> Callable[[RequestContext], Awaitable[dict[str, Any]]]:
    """``handler`` with ``backend_mode.FREE`` set while a free session is live."""

    async def marked(ctx: RequestContext) -> dict[str, Any]:
        if not live(ctx.engine):
            return await handler(ctx)
        token = backend_mode.FREE.set(True)
        try:
            return await handler(ctx)
        finally:
            backend_mode.FREE.reset(token)

    return marked
