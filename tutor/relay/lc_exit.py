# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The exit: the explanation graded for its mechanism, then the belief closed."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tutor import outage
from tutor.curriculum.modelcall import ask_model
from tutor.relay import lc_backend, lc_prompt, lc_reply, lc_state
from tutor.relay.lc_checks import MAX_TRIES, sentences

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

MAX_SENTENCES = 3


def _held(note: str) -> dict[str, Any]:
    return {"held": True, "note": note}


def _bump(ex: dict[str, Any]) -> int:
    ex["tries"] += 1
    return int(ex["tries"])


def _summary(state: lc_state.State) -> str:
    exit_ = state["exit"]
    gate, rung = state["gate"], state["rung"]
    explained = (
        "mechanism missing after 3 tries" if exit_.get("partial") else "mechanism"
    )
    belief = "none recorded"
    if state["belief"]:
        belief = "still open" if exit_.get("belief_open") else "corrected"
    rows = [
        (
            "Requirements",
            f"{gate['tries']} incomplete list(s)"
            + (", forced" if gate["forced"] else ""),
            "-",
        ),
        (
            "Code",
            f"{state.get('runs', 0)} run(s), passing"
            if state["ran_ok"]
            else "not passing",
            f"H{rung}" if rung >= 0 else "none",
        ),
        ("Explanation", explained, "-"),
        ("Belief", belief, "-"),
    ]
    lines = ["| step | what you showed | rung used |", "|---|---|---|"]
    return "\n".join([*lines, *("| " + " | ".join(r) + " |" for r in rows)])


def _finish(state: lc_state.State) -> dict[str, Any]:
    state["phase"], state["exit"]["step"] = "done", "done"
    summary = _summary(state)
    lc_state.say(state, mine=False, md=summary)
    lc_reply.log(
        state, "session_end", solved=state["ran_ok"], revealed=state["revealed"]
    )
    return {"exit": {"ok": True, "summary_md": summary}}


async def _grade(state: lc_state.State, text: str) -> dict[str, Any]:
    ex = state["exit"]
    system = lc_prompt.system(lc_backend.coach().system_prompt(state["statement_md"]))
    prompt = (
        f"{lc_prompt.EXIT_ASK}\n\nStep: {ex['step']}\n"
        f"Opening belief: {state['belief'] or 'none'}\n"
        f"kuhy's code:\n{state['last_code']}\nkuhy: {text}"
    )
    return await asyncio.to_thread(ask_model, system, prompt, lc_prompt.GRADE_SCHEMA)


async def _follow_up(
    state: lc_state.State, text: str, note: str, exit_: dict[str, Any]
) -> dict[str, Any]:
    rules = lc_reply.Rules(state["rung"], text, note, relaxed=state["revealed"])
    got = await lc_reply.ask_reply(state, text, rules)
    lc_state.say(state, mine=False, md=got["reply_md"])
    return {"reply_md": got["reply_md"], "exit": exit_}


async def _explained(
    state: lc_state.State, text: str, grade: dict[str, Any]
) -> dict[str, Any]:
    ex, ok = state["exit"], bool(grade.get("mechanism_ok"))
    if not ok and _bump(ex) < MAX_TRIES:
        missing = str(grade.get("missing", ""))[:200]
        note = (
            f"[app: the explanation misses: {missing}. Ask for that step with "
            "ONE question; do not state it.]"
        )
        return await _follow_up(state, text, note, {"ok": False, "missing": missing})
    ex["partial"] = not ok
    if not state["belief"]:
        return _finish(state)
    ex.update(step="belief", tries=0)
    return await _ask_belief(state, text)


async def _ask_belief(state: lc_state.State, text: str) -> dict[str, Any]:
    note = f"[app: {lc_prompt.BELIEF_ASK} Belief: {state['belief']}]"
    return await _follow_up(state, text, note, {"ok": True, "belief": state["belief"]})


async def solved(
    ctx: RequestContext, state: lc_state.State, text: str
) -> dict[str, Any]:
    """One ``intent:"solved"`` message; the Turn fields it adds."""
    if not (state["ran_ok"] or state["revealed"] or state.get("no_examples")):
        return _held("[run your solution on the examples first]")
    if sentences(text) > MAX_SENTENCES:
        return _held("[say it in at most 2 sentences: the key mechanism]")
    outage.ensure_available(ctx.now())
    ex, grade = state["exit"], await _grade(state, text)
    lc_state.say(state, mine=True, md=text)
    state["phase"] = "exit"
    state.setdefault("exit_ms", int(ctx.now() * 1000))  # plan_today reads it
    if ex["step"] == "explain":
        return await _explained(state, text, grade)
    if grade.get("retired"):
        return _finish(state)
    if _bump(ex) >= MAX_TRIES:
        ex["belief_open"] = True
        return _finish(state)
    return await _ask_belief(state, text)
