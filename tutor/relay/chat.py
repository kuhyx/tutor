# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Chat-lane handlers: the session kinds of ``DOCS-contract.md`` §4 on the Engine.

Credit is untouched: the engine's clock and ledger rows work exactly as for
the web page. The relay only supplies the learner's times (§7): ``created``
is RTDB server time, and the first Send press (``sent_at``) may date the
reply up to ``SEND_GRACE`` earlier, never later. The kinds that talk to
Claude fail fast with ``claude_unavailable`` while an outage window is open;
the drill kinds never need Claude.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Final
from weakref import WeakKeyDictionary

from tutor import anki, anki_collection, history, outage, resume
from tutor.clock import reply_time
from tutor.curriculum import cap
from tutor.delivery import Delivery
from tutor.drill import Drill
from tutor.relay.errors import RequestError
from tutor.relay.protocol import SLUG, SLUG_MAX
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


def _learner_time(ctx: RequestContext) -> float:
    """When the learner acted: RTDB ``created``, or the Send press within grace."""
    req = ctx.request
    sent = None if req.sent_at_ms is None else req.sent_at_ms / 1000
    return reply_time(req.created_ms / 1000, sent)


def _sessions(engine: Engine) -> Path:
    return engine.store.root / "sessions"


async def _home_pick(ctx: RequestContext) -> str | None:
    """``prefs.current_subject`` (picked on Home), if it is a slug."""
    value = await ctx.rtdb.get("prefs/current_subject")
    if isinstance(value, str) and len(value) <= SLUG_MAX and SLUG.fullmatch(value):
        return value
    return None


async def session_start(ctx: RequestContext) -> dict[str, Any]:
    """Start a session on ``card`` (or the next open card) of ``subject``.

    No ``subject``: Home's pick, else the live one (curriculum contract §6).
    ``resume`` without a card: the subject's open session first (Continue).
    ``device`` shapes the new session's opening turn; a Continue has none.
    ``lift_cap`` first lifts today's daily new cap for every device (a
    ``cap_lift`` event, once per day; ``curriculum.cap``). ``struggle``: help
    on a struggling taught ``card``, which it needs (``tutor.struggle``).
    """
    engine, body = ctx.engine, ctx.body
    if body["struggle"] and body["card"] is None:
        msg = "help on a struggling card needs the card"
        raise RequestError(msg, code="bad_request")
    if body["lift_cap"]:
        await asyncio.to_thread(cap.lift, engine.ctx)
    subject = body["subject"] or await _home_pick(ctx)
    wants_open = body["resume"] and body["card"] is None
    if wants_open and await engine.continue_subject(subject):
        return {"session": engine.session_id}
    device, struggling = str(body["device"]), bool(body["struggle"])
    await engine.start(
        body["card"], subject=subject, device=device, struggling=struggling
    )
    return {"session": engine.session_id}


async def session_resume(ctx: RequestContext) -> dict[str, Any]:
    """Continue a past session (History's Continue); the live one is left as is.

    ``device`` is validated only: resuming asks the model nothing, and the
    next ``message`` carries its own.
    """
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


async def follow_up_open(ctx: RequestContext) -> dict[str, Any]:
    """Reopen a finished session for follow-up questions (``tutor.follow_up``).

    Refused (``session_live``) while another session is live.
    """
    engine, sid = ctx.engine, str(ctx.body["session"])
    path = history.transcript_path(_sessions(engine), sid)
    if path is None:
        msg = f"no session {sid} to reopen"
        raise RequestError(msg, code="bad_request")
    await engine.follow_up_open(path)
    return {"session": engine.session_id}


async def message(ctx: RequestContext) -> dict[str, Any]:
    """The learner's message to the live session; ``rid`` is its ``msg_id``."""
    engine, req = ctx.engine, ctx.request
    _require_live(engine, req.body["session"])
    sent = None if req.sent_at_ms is None else req.sent_at_ms / 1000
    via = Delivery(sent, req.created_ms / 1000, str(req.body["device"]))
    await engine.reply(str(req.body["text"]), msg_id=req.rid, via=via)
    return {"msg": key("m", len(engine.messages))}


async def next_card(ctx: RequestContext) -> dict[str, Any]:
    """End the live session and start a new one on the next open card."""
    _require_live(ctx.engine, ctx.body["session"])
    await ctx.engine.next_card(device=str(ctx.body["device"]))
    return {"session": ctx.engine.session_id}


async def stop(ctx: RequestContext) -> dict[str, Any]:
    """End the live session for good."""
    _require_live(ctx.engine, ctx.body["session"])
    await ctx.engine.stop()
    return {}


_DRILLS: Final[WeakKeyDictionary[Engine, Drill]] = WeakKeyDictionary()


def _drill(engine: Engine) -> Drill:
    """The engine's drill (its open prompt lives as long as this process)."""
    found = _DRILLS.get(engine)
    if found is None:
        found = _DRILLS[engine] = Drill(engine.store, engine.ctx)
    return found


async def drill_next(ctx: RequestContext) -> dict[str, Any]:
    """The next multiple-choice question on a taught card (no model)."""
    return _drill(ctx.engine).next(ctx.body["subject"], ctx.now())


async def drill_answer(ctx: RequestContext) -> dict[str, Any]:
    """Grade a drill pick; its review event and any credited minute are written."""
    body = ctx.body
    pick = str(body["prompt_id"]), int(body["choice"])
    return _drill(ctx.engine).answer(*pick, _learner_time(ctx))


def _needs_claude(
    handler: Callable[[RequestContext], Awaitable[dict[str, Any]]],
) -> Callable[[RequestContext], Awaitable[dict[str, Any]]]:
    """``handler``, refused up front while Claude is known to be unavailable."""

    async def gated(ctx: RequestContext) -> dict[str, Any]:
        outage.ensure_available(ctx.now())
        return await handler(ctx)

    return gated


async def card_done(ctx: RequestContext) -> dict[str, Any]:
    """Manual override: a card done (or not); never touches credit."""
    body = ctx.body
    await ctx.engine.set_card_done(
        str(body["card"]), done=bool(body["done"]), subject=body["subject"]
    )
    return {}


async def anki_status(ctx: RequestContext) -> dict[str, Any]:
    """Credit new Anki reviews, then today's Anki figures (the Sync button)."""
    try:
        return await asyncio.to_thread(anki.status, ctx.now())
    except anki_collection.AnkiError as exc:
        raise RequestError(str(exc), code="worker_error", retry=True) from exc


CHAT_HANDLERS: Final[
    dict[str, Callable[[RequestContext], Awaitable[dict[str, Any]]]]
] = {
    "session_start": _needs_claude(session_start),
    "session_resume": _needs_claude(session_resume),
    "message": _needs_claude(message),
    "next": _needs_claude(next_card),
    "stop": stop,
    "follow_up_open": _needs_claude(follow_up_open),
    "card_done": card_done,
    "drill_next": drill_next,
    "drill_answer": drill_answer,
    "anki_status": anki_status,
}
