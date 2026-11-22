#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F22: ``#/learn/S/M`` teaches a granted module (C1, C2, C4).

``up --learn LC/prefix-sums --phase "theory LC/prefix-sums"``: the route
lands on a teaching session whose live card is the ``c4_seed.json`` card;
reopening the route reuses it (a second ``session_start``, the same session,
no new transcript). A reply more than a minute after the tutor's message pays
a verified credit row naming the subject and module (C1); "Mark card done"
then finishes the module: a verified ``module_state.json`` row reads ``done:
true`` (C2). A model turn can outlast one 60 s call, so it runs as ``send``,
``wait``, ``again`` (reopen), ``idle`` (exits 75 until the minute is up),
``reply``, ``wait``, ``check``. F23-F25 (the refusals): ``e2e_learn_gate.py``.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Final

from e2e_flow import Flow, FlowError, State
from e2e_follow_up import COMPOSER
from e2e_learn_rows import credit_paid, ledger_ids, module_done, seed, transcripts
from e2e_takeover import LC, MODULE

if TYPE_CHECKING:
    from pathlib import Path

PENDING: Final = 75
ACTIVE_S: Final = 65  # one credited minute, with margin (clock.UNIT_SECONDS)
IDLE_PER_CALL: Final = 40
# Substantive but open (it ends on a question), so the tutor neither calls it
# low effort (nothing paid) nor finishes the card itself (no tap left).
REPLY: Final = (
    "A running total is the sum of every number up to the current one. For "
    "3, 1, 4 it goes 3, then 3 + 1 = 4, then 4 + 4 = 8, so 3, 4, 8. Is the "
    "prefix sum the same thing as that running total, or does it differ?"
)
F22_PHASES: Final = ("idle", "reply")


def learn(flow: Flow, subject: str, module: str) -> None:
    """Load the app fresh on ``#/learn/subject/module`` (a new document)."""
    flow.step(f"open #/learn/{subject}/{module}")
    # A query change forces a reload: a hash-only change would not boot the app.
    bust = f"&r={time.time_ns()}"
    flow.browser.open(
        f"{flow.args.app}?db={flow.args.db}{bust}#/learn/{subject}/{module}"
    )


def _started(flow: Flow, rid: str) -> str:
    """``rid``'s session_start result is ok and names the module; its session."""
    req = (flow.db.node(f"requests/{rid}").get("req") or {}).get("body") or {}
    result = flow.result_of(rid)
    flow.note(f"body={json.dumps(req)[:160]} result={json.dumps(result)[:200]}")
    if req.get("module") != MODULE or not result.get("ok"):
        msg = f"session_start {rid} not an ok start on {MODULE}: {result}"
        raise FlowError(msg)
    return str((result.get("data") or {}).get("session"))


def _live_on(flow: Flow, sid: str) -> int:
    """``live`` is ``sid`` on the seed card; its last tutor message's ms."""
    card = seed(flow)["card"]
    live = flow.db.node("live")
    flow.step(f"live is {sid} on {card}")
    if live.get("session") != sid or live.get("card") != card:
        msg = f"live={live}, want {sid} on {card}"
        raise FlowError(msg)
    msgs = flow.db.node(f"sessions/{sid}/msgs")
    tutor = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"]
    if not tutor:
        msg = f"session {sid} has no tutor message"
        raise FlowError(msg)
    return int(tutor[-1]["at"])


def f22_send(flow: Flow) -> State:
    """The route sends a session_start for the module."""
    flow.note(f"c4 seed {seed(flow)}")
    before, files = flow.rids(), transcripts(flow)
    learn(flow, LC, MODULE)
    return {"rid": flow.request("session_start", before), "files": sorted(files)}


def f22_again(flow: Flow, state: State) -> State:
    """The first start is live; reopening the route reuses that session."""
    sid = _started(flow, str(state["rid"]))
    _live_on(flow, sid)
    new = transcripts(flow) - set(state["files"])
    flow.note(f"new transcripts after the start: {sorted(new)}")
    if new != {sid}:
        msg = f"want one new transcript {sid}, have {sorted(new)}"
        raise FlowError(msg)
    before = flow.rids()
    learn(flow, LC, MODULE)
    rid = flow.request("session_start", before)
    flow.result("session_start", before)
    if (again := _started(flow, rid)) != sid:
        msg = f"reopen started {again}, want the live {sid} reused"
        raise FlowError(msg)
    if (now := transcripts(flow) - set(state["files"])) != {sid}:
        msg = f"reopen made a second session: {sorted(now)}"
        raise FlowError(msg)
    flow.expect(COMPOSER, timeout=30)
    time.sleep(2)  # the tutor message paints after the composer
    flow.shot("learn_route")
    at = max(_live_on(flow, sid), int(time.time() * 1000))
    return state | {"sid": sid, "due": at / 1000 + ACTIVE_S}


def f22_idle(flow: Flow, state: State) -> int:
    """Wait (up to IDLE_PER_CALL s) for the reply's minute; 75 while early."""
    left = float(state["due"]) - time.time()
    flow.step(f"idle until a minute after the tutor's message ({left:.0f} s left)")
    time.sleep(max(0.0, min(left, IDLE_PER_CALL)))
    return PENDING if time.time() < float(state["due"]) else 0


def _wheel_down(flow: Flow, label: str) -> None:
    """Scroll the pane holding ``label`` down to its Send button.

    With a question list the composer pane scrolls on its own, below the
    transcript, so Send is off screen and a wheel at the viewport's centre
    moves the transcript instead.
    """
    hit = flow.browser.find(label)
    if hit is None:
        return
    for _ in range(4):
        flow.browser.call(
            "Input.dispatchMouseEvent",
            type="mouseWheel",
            x=hit["x"],
            y=hit["y"],
            deltaX=0,
            deltaY=400,
        )
        time.sleep(0.3)


def f22_reply(flow: Flow, state: State) -> State:
    """A substantive reply, sent after the minute is up."""
    if time.time() < float(state["due"]):
        msg = "reply before the minute is up: run idle first"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect(COMPOSER, timeout=30)
    before = flow.rids()
    ledger = ledger_ids(flow)
    flow.type_into(COMPOSER, REPLY)
    _wheel_down(flow, COMPOSER)
    flow.tap("Send")
    rid = flow.request("message", before)
    return state | {"rid": rid, "ledger": ledger}


def f22_check(flow: Flow, state: State) -> None:
    """The reply paid C1; Mark card done flips C2 to done."""
    flow.step("the reply's message result is ok")
    if not (result := flow.result_of(str(state["rid"]))).get("ok"):
        msg = f"reply refused: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    credit_paid(flow, state)
    flow.step("C2 before the tap: the module is not done")
    if module_done(flow):
        msg = "module already done before Mark card done"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect(COMPOSER, timeout=30)
    time.sleep(2)  # the button stays disabled until the live feed has loaded
    before = flow.rids()
    flow.tap("Mark card done", timeout=30)
    flow.request("card_done", before)
    if not flow.result("card_done", before).get("ok"):
        msg = "card_done refused"
        raise FlowError(msg)
    flow.step("C2: a verified module_state row reads done: true")
    deadline = time.monotonic() + 20
    while not module_done(flow):
        if time.monotonic() > deadline:
            msg = f"no done row for {LC}/{MODULE}"
            raise FlowError(msg)
        time.sleep(1)


def _answered(flow: Flow, rid: str) -> bool:
    """Poll ``rid``'s result for up to 45 s (no browser)."""
    flow.step(f"wait for request {rid}'s result")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if result := flow.result_of(rid):
            flow.note(f"result={json.dumps(result)[:200]}")
            return True
        time.sleep(1)
    return False


def f22(flow: Flow, phase: str, state_file: Path) -> int:
    """Run one F22 phase (module doc); 75 = call it again."""
    if phase == "send":
        state_file.write_text(json.dumps(f22_send(flow)))
        return 0
    state = json.loads(state_file.read_text())
    if phase == "wait":
        return 0 if _answered(flow, str(state["rid"])) else PENDING
    if phase == "idle":
        return f22_idle(flow, state)
    if phase == "check":
        f22_check(flow, state)
        return 0
    step = {"again": f22_again, "reply": f22_reply}[phase]
    state_file.write_text(json.dumps(step(flow, state)))
    return 0
