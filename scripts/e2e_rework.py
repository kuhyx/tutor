#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F29: the lock's ``?`` rework chat adds cards to a module.

``up --phase solve --rework LC/scans/matrix-diagonal-sum`` seeds the guard's
history of the problem and makes the module done (``e2e_rework_seed.py``).
Four calls, each under 60 s:

* ``open``: ``#/rework/LC/scans/<slug>`` sends a ``rework_open`` whose result
  counts the seeded submissions (the history is the turn's context). Saves
  the module's cards and C2 rows as the baseline. ``check`` right after
  ``open`` is the red run: no rework card yet.
* ``send``: reopens the route (the same chat) and sends what was unclear.
* ``wait``: 75 while the tutor's turn (a real model call) is pending.
* ``check``: a new card of the module carries ``tutor.source ==
  "rework:<slug>"``, a new C2 row of the module verified with the sandbox key
  reads ``done: false``, and the reopened chat is saved as
  ``<out>_rework.png`` (``app/build/screens/e2e_f29_rework.png``).
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_flow import Flow, FlowError, State
from e2e_takeover import LC
from gatelock import log_integrity

from tutor.curriculum.subject_store import SubjectStore

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.records import CardRec

PENDING: Final = 75
MODULE: Final = "scans"  # the guard's unit for array + matrix (curriculum.json)
SLUG: Final = "matrix-diagonal-sum"
SOURCE: Final = f"rework:{SLUG}"
ANSWER: Final = "Answer"  # the answer box's label (lesson_parts.AnswerBox)
# Concrete, and it asks for cards outright: an unclear message makes the tutor
# ask back with no cards (its prompt says so).
TEXT: Final = (
    "On matrix-diagonal-sum my first try was Wrong Answer: I added mat[i][i] "
    "and mat[i][n - 1 - i] for every row. What was unclear: why the centre "
    "cell of an odd n gets counted twice, and why n - 1 - i is the column of "
    "the anti-diagonal. Please add cards for both points."
)
F29_PHASES: Final = ("open",)  # send, wait, check: the shared names


def _route(flow: Flow) -> None:
    """Load the app fresh on the rework route (a query change reloads it)."""
    route = f"/rework/{LC}/{MODULE}/{SLUG}"
    flow.step(f"open #{route}")
    bust = f"&r={time.time_ns()}"
    flow.browser.open(f"{flow.args.app}?db={flow.args.db}{bust}#{route}")


def _opened(flow: Flow) -> tuple[str, dict[str, Any]]:
    """Open the route; the ``rework_open`` request id and its ok result data."""
    before = flow.rids()
    _route(flow)
    rid = flow.request("rework_open", before)
    found = flow.result("rework_open", before)
    if not found.get("ok"):
        msg = f"rework_open refused: {json.dumps(found)[:300]}"
        raise FlowError(msg)
    return rid, dict(found.get("data") or {})


def _seeded(flow: Flow) -> int:
    """How many submissions ``up --rework`` wrote to the guard's history."""
    path = flow.args.data.parent / "guard" / "history" / f"{SLUG}.json"
    return len(json.loads(path.read_text(encoding="utf-8"))["submissions"])


def _reworked(flow: Flow) -> dict[str, CardRec]:
    """The module's cards whose ``tutor`` mark names this problem's rework."""
    cards = SubjectStore(flow.args.data).cards(LC)
    return {
        cid: rec
        for cid, rec in cards.items()
        if rec.module == MODULE and rec.tutor.get("source") == SOURCE
    }


def _c2_rows(flow: Flow) -> list[dict[str, Any]]:
    """The module's C2 rows that verify with the sandbox key, in file order."""
    path = flow.args.data / "module_state.json"
    rows = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    key = flow.args.data.parent / "test.key"
    return [
        r
        for r in rows
        if (r.get("detail") or {}).get("subject") == LC
        and r["detail"].get("module") == MODULE
        and log_integrity.verify_entry_hmac(r, key_file=key)
    ]


def f29_open(flow: Flow) -> State:
    """The route opens the chat with the seeded history; the baseline."""
    rows = _c2_rows(flow)
    flow.step(f"precondition: {LC}/{MODULE} reads done: true")
    if not rows or rows[-1]["detail"]["done"] is not True:
        msg = f"{LC}/{MODULE} is not done before the flow: up --rework"
        raise FlowError(msg)
    rid, data = _opened(flow)
    flow.note(f"rework_open {rid}: {json.dumps(data)[:300]}")
    flow.expect(ANSWER, timeout=30)
    return {
        "open": rid,
        "rework_id": data.get("rework_id"),
        "history": data.get("history") or {},
        "cards": sorted(_reworked(flow)),
        "c2": [r["entry_id"] for r in rows],
    }


def f29_send(flow: Flow, state: State) -> State:
    """Reopen the chat (the same id) and send what was unclear."""
    _, data = _opened(flow)
    if data.get("rework_id") != state["rework_id"]:
        msg = f"reopen gave {data.get('rework_id')}, want {state['rework_id']}"
        raise FlowError(msg)
    flow.expect(ANSWER, timeout=30)
    time.sleep(1)  # Send enables once the open result has painted
    before = flow.rids()
    flow.type_into(ANSWER, TEXT)
    flow.tap("Send")
    return state | {"turn": flow.request("rework_turn", before)}


def f29_wait(flow: Flow, state: State) -> int:
    """Poll the turn's result for up to 45 s (no browser); 75 while pending."""
    rid = str(state["turn"])
    flow.step(f"wait for rework_turn {rid}'s result")
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if found := flow.result_of(rid):
            flow.note(f"result={json.dumps(found)[:300]}")
            return 0
        time.sleep(1)
    return PENDING


def f29_check(flow: Flow, state: State) -> None:
    """History in context, a new rework card, a new signed done: false row."""
    want = _seeded(flow)
    flow.step(f"the opened chat carried the {want} seeded submissions")
    if state["history"].get("submissions") != want:
        msg = f"rework_open history {state['history']}, want {want} submissions"
        raise FlowError(msg)
    if turn := state.get("turn"):
        found = flow.result_of(str(turn))
        flow.note(f"rework_turn result: {json.dumps(found)[:400]}")
    flow.step(f'a new {LC}/{MODULE} card carries tutor.source "{SOURCE}"')
    new = {c: r for c, r in _reworked(flow).items() if c not in set(state["cards"])}
    flow.note(f"new: {[(c, r.front, r.tutor) for c, r in new.items()]}")
    if not new:
        msg = f"no new card in {LC}/{MODULE} with tutor.source {SOURCE}"
        raise FlowError(msg)
    flow.step(f"a new verified C2 row of {LC}/{MODULE} reads done: false")
    fresh = [r for r in _c2_rows(flow) if r["entry_id"] not in set(state["c2"])]
    flow.note(f"new rows: {json.dumps(fresh)[:400]}")
    if not fresh or fresh[-1]["detail"]["done"] is not False:
        msg = f"no new verified done: false row for {LC}/{MODULE}"
        raise FlowError(msg)
    flow.step("the reopened chat shows the thread and the cards")
    _opened(flow)
    flow.expect(ANSWER, timeout=30)
    time.sleep(2)  # the thread and the card list paint after the open result
    flow.shot("rework")


def f29(flow: Flow, phase: str, state_file: Path) -> int:
    """Run one F29 phase (module doc); 75 = call it again."""
    if phase == "open":
        state_file.write_text(json.dumps(f29_open(flow)))
        return 0
    state = json.loads(state_file.read_text())
    if phase == "wait":
        return f29_wait(flow, state)
    if phase == "check":
        f29_check(flow, state)
        return 0
    if phase != "send":
        msg = f"F29 has no phase {phase!r}: open, send, wait, check"
        raise FlowError(msg)
    state_file.write_text(json.dumps(f29_send(flow, state)))
    return 0
