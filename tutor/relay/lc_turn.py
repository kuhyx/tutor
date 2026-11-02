# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``lc_turn``: one message to the coach, every gate applied in code."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Final

from tutor import outage
from tutor.curriculum.modelcall import ask_model
from tutor.relay import lc_backend, lc_checks, lc_exit, lc_prompt, lc_reply, lc_state
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

type Json = Any
HINTS: Final = {"hint": 1, "hint!": 2}


def _held(state: lc_state.State, note: str) -> dict[str, Any]:
    return {"state": lc_state.view(state), "held": True, "note": note}


def _open(state: lc_state.State) -> bool:
    return bool(state["gate"]["open"])


def _gate_note(verdict: str, missing: tuple[str, ...], state: lc_state.State) -> str:
    tries = state["gate"]["tries"]
    if verdict != "incomplete":
        tail = "" if verdict == "pass" else " (unverified)"
        return f"[requirements accepted{tail}: code is open]"
    names = ", ".join(missing)
    if state["gate"]["forced"]:
        return f"[still incomplete ({names}): code accepted anyway]"
    return (
        f"[incomplete: it does not yet say {names}; {tries} of {lc_checks.MAX_TRIES}]"
    )


async def _gate_message(
    state: lc_state.State, text: str, prefix: str
) -> dict[str, Any]:
    kind, gate = state["kind"], state["gate"]
    want = lc_checks.GATE_PREFIX[kind]
    if prefix != want:
        return _held(state, f"[this is a {kind} problem: start with {want}:]")
    statement = state["statement_md"]
    if kind == "sql":
        verdict, missing = lc_checks.shape_verdict(statement, text)
    else:
        verdict, missing = await asyncio.to_thread(
            lc_backend.coach().check_req, statement, text, ask_model
        )
    state["reqs"].append(text.strip())
    lc_reply.log(state, "req", text=text.strip())
    lc_reply.log(state, "req_check", verdict=verdict, missing=list(missing))
    gate["tries"] += verdict == "incomplete"
    gate["forced"] = verdict == "incomplete" and gate["tries"] >= lc_checks.MAX_TRIES
    gate["open"] = verdict != "incomplete" or gate["forced"]
    state["phase"] = "work" if gate["open"] else state["phase"]
    note = _gate_note(verdict, missing, state)
    lc_state.say(state, mine=True, md=text)
    state["thread"].append({"mine": False, "md": note, "note": True})
    return {"state": lc_state.view(state), "note": note}


def _frustration(state: lc_state.State, text: str) -> dict[str, Any]:
    rung = f"H{state['rung']}" if state["rung"] >= 0 else "none"
    reply = (
        f"I have been going in circles with you: {state['turns']} turns, rung "
        f"{rung}. Pick one: write the whole function now and I run it, one "
        "bigger hint, or reveal."
    )
    lc_state.say(state, mine=True, md=text)
    lc_state.say(state, mine=False, md=reply)
    return {
        "state": lc_state.view(state),
        "reply_md": reply,
        "choices": lc_checks.CHOICES,
    }


def _write_it(state: lc_state.State, text: str) -> dict[str, Any]:
    state["gate"].update(open=True, forced=True)
    state["phase"] = "work" if state["phase"] == "gate" else state["phase"]
    reply = "Paste your whole function and I will run it on the examples."
    lc_state.say(state, mine=True, md=text)
    lc_state.say(state, mine=False, md=reply)
    return {"state": lc_state.view(state), "reply_md": reply}


async def _coach_turn(
    ctx: RequestContext, state: lc_state.State, text: str, word: str
) -> dict[str, Any]:
    outage.ensure_available(ctx.now())
    revealed, hint = word == "reveal", HINTS.get(word, 0)
    if revealed:
        lc_reply.log(state, "reveal")
        state.update(revealed=True, phase="exit")
        state.setdefault("exit_ms", int(ctx.now() * 1000))  # plan_today reads it
    elif lc_checks.is_code(text, state["kind"]):
        if not state["code_seen"]:
            extra = {"req_incomplete": True} if state["gate"]["forced"] else {}
            lc_reply.log(state, "code", **extra)
        state.update(code_seen=True, last_code=text)
    over = state["turns"] >= lc_state.budget(state)
    note = lc_prompt.REVEAL if revealed else (lc_prompt.BUDGET_NOTE if over else "")
    ceiling = lc_checks.rung_ceiling(state["rung"], hint=hint, failed=state["failed"])
    rules = lc_reply.Rules(ceiling, text, note, relaxed=revealed)
    got = await lc_reply.ask_reply(state, text, rules)
    reply = lc_checks.reprint(got["reply_md"], state["last_code"], state["last_table"])
    new = -1 if revealed else lc_checks.rank(got["rung"])
    if new >= 0:
        lc_reply.log(state, "rung", rung=got["rung"])
        state["failed"] = state["failed"] and new <= state["rung"]
        state["rung"] = max(state["rung"], new)
    if got["belief"] and not state["belief"]:
        state["belief"] = got["belief"]
    state["turns"] += 1
    lc_state.say(state, mine=True, md=text)
    lc_state.say(state, mine=False, md=reply)
    out: dict[str, Any] = {"state": lc_state.view(state), "reply_md": reply}
    if over and not revealed:
        out["banner"] = "budget"
    return out


async def _word(
    ctx: RequestContext, state: lc_state.State, text: str, intent: str
) -> dict[str, Any] | None:
    word = text.strip().lower()
    if intent == "solved":
        return await lc_exit.solved(ctx, state, text)
    if word in {"reveal", *HINTS}:
        return await _coach_turn(ctx, state, text, word)
    if word == "write it":
        return _write_it(state, text)
    angry, state["confused"] = lc_checks.frustrated(text, state["confused"])
    return _frustration(state, text) if angry else None


async def _route(
    ctx: RequestContext, state: lc_state.State, text: str, intent: str
) -> dict[str, Any]:
    if (out := await _word(ctx, state, text, intent)) is not None:
        return out
    prefix = lc_checks.gate_prefix(text)
    if prefix is not None and not _open(state):
        return await _gate_message(state, text, prefix)
    if not _open(state) and lc_checks.is_code(text, state["kind"]):
        note = "[code held back: write the requirement list first]"
        return _held(state, note)
    return await _coach_turn(ctx, state, text, text.strip().lower())


async def lc_turn(ctx: RequestContext) -> Json:
    """One message to the coach: gate, hint, reveal, chat or exit."""
    body = ctx.body
    state = lc_state.load(body["lc_id"])
    if state["phase"] == "done":
        msg = "this coach session is finished"
        raise RequestError(msg, code="bad_request")
    out = await _route(ctx, state, body["text"], body["intent"])
    if not out.get("held"):
        lc_state.save(body["lc_id"], state, int(ctx.now() * 1000))
    lc_reply.heartbeat()
    out["state"] = lc_state.view(state)
    return out
