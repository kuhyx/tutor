#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F28: the second unit goes through the module gate first.

LC's unit order puts prefix-sums before stack-queue. Each sandbox is a fresh
``up --unit-gate MODE``; its ``seed`` also stops LC's newest session.

* day one (``--unit-gate fresh --phase "theory $LC/prefix-sums"``): ``send``,
  ``wait``, ``lesson`` (an ok start on a prefix-sums card), ``idle``,
  ``reply``, ``wait``, ``paid`` (a C1 credit row naming the module).
* the next unit (``--unit-gate taught --phase "theory $LC/stack-queue"``):
  ``review`` (refused, the two unpassed prefix-sums cards as gate_cards; the
  review opens, Good twice, the app starts again), ``wait``, ``check`` (the
  live card is in stack-queue).
* SOLVE (``--unit-gate taught --phase solve``): ``solve`` (the same refusal
  and review, then no_card_left with no gate_cards; the plan shows; live and
  the transcripts are unchanged).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import TYPE_CHECKING, Any, Final
import uuid

from e2e_flow import FlowError
from e2e_follow_up import COMPOSER
from e2e_gate import UNPASSED, pass_review
from e2e_learn import ACTIVE_S, PENDING, _answered, f22_idle, f22_reply, learn
from e2e_learn_rows import credit_paid, transcripts
from e2e_phase import quiet_today, untaught
from e2e_seed import GAP_MS, GOOD, SeedError, _stop_newest
from e2e_takeover import LC, LOCK, MODULE, text_below

from tutor.curriculum import rules
from tutor.curriculum.context import Context
from tutor.curriculum.eventlog import review_event, worker_event
from tutor.curriculum.fold import fold

if TYPE_CHECKING:
    from e2e_flow import Flow, State

_logger = logging.getLogger(__name__)
NEXT: Final = "stack-queue"  # the unit after prefix-sums in the guard's order
F28_PHASES: Final = ("lesson", "paid", "review", "solve")


def seed(data: Path, mode: str, now: int) -> dict[str, Any]:
    """Day one for LC; ``taught``: then prefix-sums taught, two cards unpassed."""
    quiet_today(data)  # also refuses the real data dir
    ctx = Context(data, device=str(uuid.uuid4()))
    plan = ctx.subjects.plan(LC)
    module = plan.module(MODULE) if plan else None
    if plan is None or module is None:
        msg = f"{LC} has no module {MODULE}"
        raise SeedError(msg)
    cards = ctx.subjects.cards(LC)
    folded = fold(ctx.log.read())
    worker = (data / "device_id").read_text(encoding="utf-8").strip()
    back = sorted(folded.taught_ids(LC))  # taken back: day one whatever kuhy did
    events = [
        worker_event("untaught", (LC, c), dev=worker, at=now - 3 * GAP_MS) for c in back
    ]
    view = rules.View(LC, plan, cards)
    counted = rules.counted(view, MODULE, folded)
    ids = [c for c, _ in counted] if mode == "taught" else []
    for cid in ids:
        ref = (LC, cid)
        events.append(worker_event("taught", ref, dev=worker, at=now - 2 * GAP_MS))
        if cid not in ids[-UNPASSED:]:  # reviewed by a fresh "app" device
            span = (now - GAP_MS - 5000, now - GAP_MS)
            rev = cards[cid].rev
            events.append(review_event(ref, GOOD, dev=ctx.device, span=span, rev=rev))
    ctx.log.append(events)
    _stop_newest(data, LC)
    out = {
        "mode": mode,
        "plan": [m.id for m in plan.modules],
        "module_title": module.title,
        "unpassed": ids[-UNPASSED:],
    }
    (data.parent / "f28_seed.json").write_text(json.dumps(out), encoding="utf-8")
    return out


def _seed_of(flow: Flow, mode: str) -> dict[str, Any]:
    path = Path(flow.args.data).parent / "f28_seed.json"
    found = dict(json.loads(path.read_text(encoding="utf-8")))
    if found["mode"] != mode:
        msg = f"this phase needs up --unit-gate {mode}, not {found['mode']}"
        raise FlowError(msg)
    return found


def _ok_on(flow: Flow, rid: str, module: str) -> str:
    body = (flow.db.node(f"requests/{rid}").get("req") or {}).get("body") or {}
    result = flow.result_of(rid)
    flow.note(f"body={json.dumps(body)[:160]} result={json.dumps(result)[:300]}")
    if body.get("module") != module or not result.get("ok"):
        msg = f"not an ok start on {module}: {result}"
        raise FlowError(msg)
    return str((result.get("data") or {}).get("session"))


def _live_in(flow: Flow, sid: str, module: str) -> str:
    live = flow.db.node("live")
    cards = Context(Path(flow.args.data), device="e2e").subjects.cards(LC)
    card = str(live.get("card"))
    flow.step(f"live is {sid} on a card of {module}")
    if live.get("session") != sid or card not in cards or cards[card].module != module:
        msg = f"live={live}, want {sid} on a {module} card"
        raise FlowError(msg)
    return card


def _send(flow: Flow) -> State:
    found = _seed_of(flow, "fresh")
    ctx = Context(Path(flow.args.data), device=str(uuid.uuid4()))
    taught = fold(ctx.log.read()).taught_ids(LC)
    flow.step(f"{MODULE} is not the plan's first module and no LC card is taught")
    if found["plan"].index(MODULE) == 0 or taught:
        msg = "not day one"
        raise FlowError(msg)
    before = flow.rids()
    learn(flow, LC, MODULE)
    rid = flow.request("session_start", before)
    return {"rid": rid, "cards": untaught(ctx, LC, MODULE)}


def _lesson(flow: Flow, state: State) -> State:
    sid = _ok_on(flow, str(state["rid"]), MODULE)
    if _live_in(flow, sid, MODULE) not in state["cards"]:
        msg = "the live card was taught already"
        raise FlowError(msg)
    before = flow.rids()
    learn(flow, LC, MODULE)  # what the lock's button opens, once more
    flow.result("session_start", before)
    flow.expect(COMPOSER, timeout=30)
    time.sleep(2)
    flow.shot("lesson")
    msgs = flow.db.node(f"sessions/{sid}/msgs")
    at = max([int(m["at"]) for m in msgs.values() if m.get("role") == "tutor"] or [0])
    due = max(at, int(time.time() * 1000)) / 1000 + ACTIVE_S
    return state | {"sid": sid, "due": due}


def _paid(flow: Flow, state: State) -> None:
    if not (result := flow.result_of(str(state["rid"]))).get("ok"):
        msg = f"reply refused: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    credit_paid(flow, state)  # needs state["ledger"] (f22_reply) and ["sid"]


def _gated_start(flow: Flow, unpassed: list[str]) -> set[str]:
    before = flow.rids()
    learn(flow, LC, NEXT)
    result = flow.start_result(before)
    after = flow.rids()
    cards = result.get("gate_cards") or []
    if result.get("code") != "no_card_left" or sorted(cards) != sorted(unpassed):
        msg = f"want no_card_left with gate_cards {unpassed}, got {result}"
        raise FlowError(msg)
    return after


def _review(flow: Flow) -> State:
    found = _seed_of(flow, "taught")
    after = _gated_start(flow, found["unpassed"])
    pass_review(flow, found["module_title"])
    return {"rid": flow.request("session_start", after, timeout=30)}


def _check(flow: Flow, state: State) -> None:
    _live_in(flow, _ok_on(flow, str(state["rid"]), NEXT), NEXT)
    flow.screen("/session")
    flow.expect(COMPOSER, timeout=30)
    flow.shot("next_unit")


def _solve(flow: Flow) -> None:
    found = _seed_of(flow, "taught")
    live, files = flow.db.node("live"), transcripts(flow)
    after = _gated_start(flow, found["unpassed"])
    pass_review(flow, found["module_title"])
    rid = flow.request("session_start", after, timeout=30)
    deadline = time.monotonic() + 30
    while not (result := flow.result_of(rid)) and time.monotonic() < deadline:
        time.sleep(0.5)
    if result.get("code") != "no_card_left" or result.get("gate_cards") != []:
        msg = f"want no_card_left with no gate_cards, got {result}"
        raise FlowError(msg)
    folded = fold(Context(Path(flow.args.data), device="e2e").log.read())
    if left := [c for c in found["unpassed"] if not rules.reviewed(folded.card(LC, c))]:
        msg = f"not passed in the worker's log: {left}"
        raise FlowError(msg)
    if not text_below(flow.browser, LOCK, 30) or COMPOSER in flow.browser.page_text():
        msg = "no plan"
        raise FlowError(msg)
    if (live, files) != (flow.db.node("live"), transcripts(flow)):
        msg = "live or the transcripts changed in SOLVE"
        raise FlowError(msg)


def f28(flow: Flow, phase: str, state_file: Path) -> int:
    """Run one F28 phase (module doc); 75 = call it again."""
    if phase == "solve":
        _solve(flow)
        return 0
    if phase in {"send", "review"}:
        first = _send(flow) if phase == "send" else _review(flow)
        state_file.write_text(json.dumps(first))
        return 0
    state = json.loads(state_file.read_text())
    if phase == "wait":
        return 0 if _answered(flow, str(state["rid"])) else PENDING
    if phase == "idle":
        return f22_idle(flow, state)
    if phase in {"paid", "check"}:
        (_paid if phase == "paid" else _check)(flow, state)
        return 0
    step = {"lesson": _lesson, "reply": f22_reply}[phase]
    state_file.write_text(json.dumps(step(flow, state)))
    return 0


def main() -> int:
    """CLI entry: ``seed DATA fresh|taught`` (module doc)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("what", choices=["seed"])
    parser.add_argument("data", type=Path)
    parser.add_argument("mode", choices=["fresh", "taught"])
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stderr, format="%(message)s")
    try:
        found = seed(args.data, args.mode, int(time.time() * 1000))
    except SeedError as err:
        _logger.warning("e2e_unit_gate: %s", err)  # `up` stops on exit 1
        return 1
    sys.stdout.write(f"e2e seed F28: {json.dumps(found)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
