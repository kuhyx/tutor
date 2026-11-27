#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's Claude-check phases (C8), after ``gate`` on ``up --fallback gate``.

``gate`` left two cards read without Claude (taught, ``unchecked``). With the
outage closed and a real model:

* ``check`` taps Home's Continue learning and saves the ``session_start`` id;
* ``checkwait`` (75 = again) waits for the latest saved request's result;
* ``checkfirst``: the live card is one of the unchecked ones and its system
  prompt carries the check section (no new card first); then it answers with
  the card's own back and saves the ``message`` id;
* ``checkwait`` again, then ``checkdone``: the tutor ended the card and the
  log has its ``checked`` event (a right answer: no Again review);
* ``checknext`` taps Next card (``checkwait``), ``checkwrong`` answers the
  other unchecked card wrongly (``checkwait``); the tutor teaches it in full,
  so ``checkreply`` answers with the card's back (``checkwait``, repeat until
  the tutor ends it), and ``checkagain``: a review rated Again and ``checked``.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_fallback_checks import log_events
from e2e_fallback_free import freewait
from e2e_fallback_hold import seeded_read
from e2e_flow import FlowError
from e2e_follow_up import COMPOSER

from tutor.check_flagged import SECTION
from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from e2e_flow import Flow

HEADER: Final = SECTION.splitlines()[0]
WRONG: Final = "I have no idea, maybe it is about the weather."


def _state(flow: Flow) -> dict[str, Any]:
    return dict(json.loads(Path(flow.args.state).read_text(encoding="utf-8")))


def _save(flow: Flow, state: dict[str, Any]) -> None:
    Path(flow.args.state).write_text(json.dumps(state), encoding="utf-8")


def check(flow: Flow) -> int:
    """Home's Continue learning starts a Claude session (the outage is closed)."""
    flow.home()
    before = flow.rids()
    since = int(time.time() * 1000)
    flow.tap("Continue learning", timeout=30)
    rid = flow.request("session_start", before)
    _save(flow, {"rid": rid, "since": since, "read": seeded_read(flow)})
    return 0


def _last_prompt(flow: Flow) -> str:
    path = Path(flow.args.data).parent / "prompts.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return str(json.loads(lines[-1])["prompt"]) if lines else ""


def checkfirst(flow: Flow, *, wrong: bool = False) -> int:
    """The session opened an unchecked card with the check section; answer it."""
    state = _state(flow)
    state["read"] = [c for c in state["read"] if c != state.get("card")]
    if not (result := flow.result_of(str(state["rid"]))).get("ok"):
        msg = f"session_start failed: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    live = flow.db.node("live")
    card = str(live.get("card"))
    flow.step(f"the live card {card} is one of the unchecked {state['read']}")
    if card not in state["read"]:
        msg = f"live card {card} is not an unchecked one: {state['read']}"
        raise FlowError(msg)
    flow.step("its system prompt carries the check section")
    if HEADER not in _last_prompt(flow):
        msg = f"no {HEADER!r} in the session's system prompt"
        raise FlowError(msg)
    msgs = flow.db.node(f"sessions/{live['session']}/msgs")
    tutor = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"]
    flow.note(f"tutor: {str(tutor[-1].get('text') if tutor else '')[:300]!r}")
    back = Context(flow.args.data).subjects.cards(flow.args.subject)[card].back
    flow.screen("/session")
    flow.expect(COMPOSER, timeout=30)
    flow.shot("check")
    before = flow.rids()
    flow.type_into(COMPOSER, WRONG if wrong else back)
    flow.tap("Send")
    _save(flow, state | {"card": card, "rid": flow.request("message", before)})
    return 0


def checkdone(flow: Flow) -> int:
    """The right answer cleared the mark: ``checked``, no Again review."""
    state = _state(flow)
    card, since = str(state["card"]), int(state["since"])
    mine = [
        e
        for e in log_events(Path(flow.args.data))
        if e.get("c") == card and int(e.get("at", 0)) >= since
    ]
    kinds = [str(e["k"]) for e in mine]
    flow.step(f"{card}: the log has checked and no Again review: {kinds}")
    again = [e for e in mine if e["k"] == "review" and e.get("r") == 1]
    if "checked" not in kinds or again:
        live = flow.db.node("live")
        msgs = flow.db.node(f"sessions/{live.get('session')}/msgs")
        last = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"][-1:]
        flow.note(f"last tutor: {str(last[0].get('text') if last else '')[:400]!r}")
        msg = f"want checked and no Again for {card}, got {kinds}"
        raise FlowError(msg)
    flow.screen("/session")
    time.sleep(3)
    flow.shot("checkdone")
    return 0


def checknext(flow: Flow) -> int:
    """Next card after the checked one: the session opens the other unchecked."""
    state = _state(flow)
    flow.screen("/session")
    before = flow.rids()
    flow.tap("Next card", timeout=30)
    _save(flow, state | {"rid": flow.request("next", before)})
    return 0


def checkreply(flow: Flow) -> int:
    """Answer the re-taught card with its own back, so the tutor can end it."""
    state = _state(flow)
    back = Context(flow.args.data).subjects.cards(flow.args.subject)[state["card"]]
    flow.screen("/session")
    flow.expect(COMPOSER, timeout=30)
    before = flow.rids()
    flow.type_into(COMPOSER, back.back)
    flow.tap("Send")
    _save(flow, state | {"rid": flow.request("message", before)})
    return 0


def checkagain(flow: Flow) -> int:
    """A wrong answer: an Again review and ``checked``; the card stays live."""
    state = _state(flow)
    card, since = str(state["card"]), int(state["since"])
    mine = [
        e
        for e in log_events(Path(flow.args.data))
        if e.get("c") == card and int(e.get("at", 0)) >= since
    ]
    kinds = [f"{e['k']}:{e.get('r', '')}" for e in mine]
    flow.step(f"{card}: the log has review:1 and checked: {kinds}")
    live = flow.db.node("live")
    if "review:1" not in kinds or "checked:" not in kinds:
        msgs = flow.db.node(f"sessions/{live.get('session')}/msgs")
        last = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"][-1:]
        flow.note(f"last tutor: {str(last[0].get('text') if last else '')[:400]!r}")
        msg = f"want an Again review and checked for {card}, got {kinds}"
        raise FlowError(msg)
    flow.screen("/session")
    time.sleep(3)
    flow.shot("checkagain")
    return 0


PHASES: Final[dict[str, Any]] = {
    "check": check,
    "checkwait": freewait,
    "checkfirst": checkfirst,
    "checkdone": checkdone,
    "checknext": checknext,
    "checkwrong": lambda flow: checkfirst(flow, wrong=True),
    "checkreply": checkreply,
    "checkagain": checkagain,
}
