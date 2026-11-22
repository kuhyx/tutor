#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F31: a refused ``card_done`` never shows "this card is done".

Runs on ``e2e_sandbox.sh up --scripted`` (the model is a queue the flow
writes, ``e2e_script_session.py``; the engine, relay and app are real). One
call per phase, each under 60 s:

* ``rewrite``: a session starts on an open card C, its prerequisite Y is
  then marked not done (a second device's ``card_done`` request), and the
  model answers ``card_done``. The page shows only the model's rewrite, the
  rewrite prompt names Y by its front, C stays untaught and the ledger gains
  no ``theory-done`` row.
* ``fallback`` (after ``rewrite``, same sandbox): the rewrite claims done
  again; the page shows the lock glyph and Y's front, no draft.
* ``module`` (a fresh ``up --scripted --learn $LC/M --phase "theory $LC/M"``
  with ``E2E_SUBJECT=$LC``): the draft is held while the flow moves the guard
  to ``solve``; the rewrite prompt names the module by its plan title.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Final

from e2e_cdp import Browser, CdpError
import e2e_done_refusal_steps as steps
from e2e_failures import _await, _send
from e2e_flow import Flow, FlowError, State
from e2e_phase import write as write_phase
import e2e_script_session as script

from tutor import done_refusal
from tutor.curriculum.context import Context

_logger = logging.getLogger(__name__)
PHASES: Final = ("rewrite", "fallback", "module")
DRAFT: Final = "Great work, this card is done!"
DRAFT2: Final = "Perfect, this card is finished, on to the next!"


def rewrite(flow: Flow) -> State:
    """A prerequisite is untaught at card_done: the rewrite is the bubble."""
    flow.precheck()
    subject = str(flow.args.subject)
    pairs = steps.candidates(flow, subject)[:6]
    # Lazy: the first pair whose session starts (each start replaces the last).
    started = (p for p in pairs if steps.start(flow, subject, {"card": p[0]}).get("ok"))
    if (pair := next(started, None)) is None:
        msg = f"no open card with taught requires started in {subject}"
        raise FlowError(msg)
    card, need = pair
    sid = str(flow.db.node("live")["session"])
    flow.step(f"a second device marks the prerequisite {need} not done")
    undo = {"subject": subject, "card": need, "done": False}
    if not _await(flow, _send(flow, "card_done", undo)).get("ok"):
        msg = f"card_done {need} false was refused"
        raise FlowError(msg)
    front = steps.front(flow, subject, need)
    state: State = {"sid": sid, "subject": subject, "card": card, "need": need}
    state |= {"front": front, "theory_rows": steps.theory_rows(flow), "shot": "rewrite"}
    said = f'This card stays open until "{front}" is taught. Switch to it now?'
    steps.ask_done(flow, [{"message": DRAFT, "card_done": True}, {"message": said}])
    steps.prompted(flow, f'"{front}"', "card_done was refused", banned=need)
    steps.verify(flow, state, said, [DRAFT], "rewritten")
    return state


def fallback(flow: Flow, state: State) -> None:
    """The rewrite claims done again: the lock glyph and the front show."""
    again = "Still done, well done!"
    steps.ask_done(
        flow,
        [{"message": DRAFT2, "card_done": True}, {"message": again, "card_done": True}],
    )
    state["shot"] = "fallback"
    lock = done_refusal.fallback_text([str(state["front"])])
    steps.verify(flow, state, lock, [DRAFT, DRAFT2, again], "fallback")


def module(flow: Flow) -> None:
    """C3 refuses the module while the draft is held: the title is named."""
    flow.precheck()
    subject = str(flow.args.subject)
    if not steps.start(flow, subject, {}).get("ok"):
        msg = f"no session started in {subject} (up --learn + --phase?)"
        raise FlowError(msg)
    live = flow.db.node("live")
    card = str(live["card"])
    rec = Context(flow.args.data).subjects.cards(subject)[card]
    plan = Context(flow.args.data).subjects.plan(subject)
    title = next(m.title for m in plan.modules if m.id == rec.module) if plan else ""
    state: State = {"sid": live["session"], "subject": subject, "card": card}
    state |= {"theory_rows": steps.theory_rows(flow), "shot": "module"}
    flag = flow.args.data.parent / "release.flag"
    flag.unlink(missing_ok=True)
    said = f'"{title}" stays closed for now. Want an open card instead?'
    entries: list[dict[str, Any]] = [
        {"message": DRAFT, "card_done": True, "hold": str(flag)},
        {"message": said},
    ]
    rid = steps.send_message(flow, entries, "I get it, mark this card done")
    flow.step("the draft is held; the guard moves to solve")
    deadline = time.monotonic() + 20
    while not script.held(steps.queue(flow)).exists() and time.monotonic() < deadline:
        time.sleep(0.2)
    sandbox = flow.args.data.parent
    write_phase(sandbox / "theory_phase.json", sandbox / "test.key", "solve", [])
    flag.write_text("go", encoding="utf-8")
    if not _await(flow, rid, 30).get("ok"):
        msg = "the message was refused"
        raise FlowError(msg)
    steps.prompted(flow, f'"{title}"', "closed for now")
    steps.verify(flow, state, said, [DRAFT], "rewritten")


def run(flow: Flow, phase: str) -> None:
    """One phase; ``rewrite`` saves the state ``fallback`` reads."""
    state_file = Path(flow.args.state)
    if phase == "rewrite":
        state_file.write_text(json.dumps(rewrite(flow)), encoding="utf-8")
    elif phase == "fallback":
        fallback(flow, json.loads(state_file.read_text(encoding="utf-8")))
    else:
        module(flow)


def main() -> int:
    """CLI entry: the arguments of ``e2e_drive.py`` (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=["F31"])
    parser.add_argument("phase", choices=PHASES)
    for name in ("--app", "--db", "--card", "--out", "--state", "--session"):
        parser.add_argument(name)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--focus", type=Path)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--display", default=":97")
    parser.add_argument("--size", default="2560x1440")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    width, height = (int(n) for n in args.size.split("x"))
    with Browser(args.display, Path(f"{args.out}_chrome.log"), (width, height)) as b:
        flow = Flow(args, b)
        try:
            run(flow, args.phase)
        except (FlowError, CdpError, OSError, KeyError, ValueError) as err:
            _logger.warning("FAIL F31 %s step %d: %s", args.phase, flow.n, err)
            flow.shot("fail")
            return 1
    _logger.info("PASS F31 %s", args.phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
