# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Chat-lane handlers: the session kinds of ``DOCS-contract.md`` §4 on the Engine.

Credit is untouched: the engine's clock and ledger rows work exactly as for
the web page. The relay only supplies the learner's times (§7): ``created``
is RTDB server time, and the first Send press (``sent_at``) may date the
reply up to ``SEND_GRACE`` earlier, never later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tutor import history, resume
from tutor.relay.errors import RequestError
from tutor.relay.views import key

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from tutor.engine import Engine
    from tutor.relay.context import RequestContext


def _not_live(sid: str) -> RequestError:
    return RequestError(
        f"session {sid} is not live; continue it first", code="not_live"
    )


def _require_live(engine: Engine, sid: object) -> None:
    if not engine.session_id or engine.session_id != sid:
        raise _not_live(str(sid))


def _sessions(engine: Engine) -> Path:
    return engine.store.root / "sessions"


async def session_start(ctx: RequestContext) -> dict[str, Any]:
    """Start a session on ``card`` (or the next open card) of ``subject``."""
    engine = ctx.engine
    await engine.start(ctx.body["card"], subject=ctx.body["subject"])
    return {"session": engine.session_id}


async def session_resume(ctx: RequestContext) -> dict[str, Any]:
    """Continue a past session (History's Continue); the live one is left as is."""
    engine, sid = ctx.engine, str(ctx.body["session"])
    if sid == engine.session_id:
        return {"session": sid}
    path = history.transcript_path(_sessions(engine), sid)
    replayed = resume.replay(path) if path else None
    if path is None or replayed is None:
        msg = f"no session {sid} to continue"
        raise RequestError(msg, code="bad_request")
    conv = replayed.conversation
    if conv.stopped:
        msg = "that session was stopped; use Repeat instead"
        raise RequestError(msg, code="not_live")
    await engine.resume_session(path)
    return {"session": engine.session_id}


async def message(ctx: RequestContext) -> dict[str, Any]:
    """The learner's message to the live session; ``rid`` is its ``msg_id``."""
    engine, req = ctx.engine, ctx.request
    _require_live(engine, req.body["session"])
    sent = None if req.sent_at_ms is None else req.sent_at_ms / 1000
    await engine.reply(
        str(req.body["text"]),
        msg_id=req.rid,
        sent_at=sent,
        received=req.created_ms / 1000,
    )
    return {"msg": key("m", len(engine.messages))}


async def next_card(ctx: RequestContext) -> dict[str, Any]:
    """End the live session and start a new one on the next open card."""
    _require_live(ctx.engine, ctx.body["session"])
    await ctx.engine.next_card()
    return {"session": ctx.engine.session_id}


async def stop(ctx: RequestContext) -> dict[str, Any]:
    """End the live session for good."""
    _require_live(ctx.engine, ctx.body["session"])
    await ctx.engine.stop()
    return {}


async def card_done(ctx: RequestContext) -> dict[str, Any]:
    """Manual override: a card done (or not); never touches credit."""
    body = ctx.body
    await ctx.engine.set_card_done(
        str(body["card"]), done=bool(body["done"]), subject=body["subject"]
    )
    return {}


CHAT_HANDLERS: Final[
    dict[str, Callable[[RequestContext], Awaitable[dict[str, Any]]]]
] = {
    "session_start": session_start,
    "session_resume": session_resume,
    "message": message,
    "next": next_card,
    "stop": stop,
    "card_done": card_done,
}
