#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows: tap the real web build, assert on the emulator, screenshot.

Run by ``scripts/e2e_sandbox.sh flow <F1|F2|F3|F4> [send|wait|check]``
against a sandbox that is ``up``. Every step is printed before it runs, so on
failure the last line names it; a failure also saves ``<out>_fail.png``.
Exit 0 = PASS.

* F1 Continue learning: Home -> "Continue learning" -> the subject's next
  card (``--card``) is live and its first tutor message is on screen.
* F2 daily cap (sandbox ``up --new-cap N``, N <= today's new cards): the
  same tap ends on the blocked panel with "Learn more anyway"; tapping it
  starts ``--card`` with a tutor message.
* F3, F4 follow-up questions (``e2e_follow_up.py``).
* F5 help on a struggling card (``e2e_struggle.py``; phased like F1).
* F6 the carry-over bank (``e2e_carry.py``): ``check``, then ``again`` after
  ``e2e_sandbox.sh restart``.

A tutor turn (high effort, thinking, up to 90 s of research) can outlast one
60 s call, so F1, F3 and F4 run in phases, one call each: ``send`` taps up
to the request and saves ``--state``; ``wait`` polls the emulator (no
browser) for up to ``--wait`` s and exits 75 (``PENDING``) while the worker
is still on it: call it again; ``check`` reopens the app and asserts. No
phase runs all three in one call.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import TYPE_CHECKING

from e2e_carry import f6_again, f6_check
from e2e_cdp import Browser, CdpError
from e2e_flow import Emulator, Flow, FlowError, State
from e2e_follow_up import f3_check, f3_send, f4_check, f4_send
from e2e_struggle import f5_check, f5_send

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)
PENDING = 75  # wait: the worker has not answered yet; call wait again


def f1_send(flow: Flow) -> State:
    """Home -> Continue learning: the session_start request is sent."""
    flow.precheck(capped=False)
    flow.home()
    before = flow.rids()
    flow.tap("Continue learning", timeout=30)
    return {"rid": flow.request("session_start", before)}


def f1_check(flow: Flow, state: State) -> None:
    """The next card started with a tutor message."""
    flow.step("the session_start result is ok")
    result = flow.result_of(str(state["rid"]))
    print(f"  result={json.dumps(result)[:300]}")
    if not result.get("ok"):
        flow.home()
        flow.shot("blocked")
        msg = f"session_start refused: {result.get('code')}: {result.get('error')}"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect_card()
    flow.shot("started")


def f2(flow: Flow) -> None:
    """At the cap: the call to action is shown and lifts the cap."""
    flow.precheck(capped=True)
    flow.home()
    before = flow.rids()
    flow.tap("Continue learning", timeout=30)
    result = flow.start_result(before)
    if result.get("code") != "daily_new_cap":
        msg = f"want daily_new_cap, got {json.dumps(result)[:300]}"
        raise FlowError(msg)
    flow.step('"Learn more anyway" is shown')
    if flow.browser.wait_for("Learn more anyway", 15) is None:
        msg = f"no call to action; saw: {flow.browser.page_text()[:400]!r}"
        raise FlowError(msg)
    flow.shot("blocked")
    before = flow.rids()
    flow.tap("Learn more anyway")
    result = flow.start_result(before)
    if not result.get("ok"):
        msg = f"lift_cap start refused: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    flow.expect_card()
    flow.shot("started")


PHASED: dict[str, tuple[Callable[[Flow], State], Callable[[Flow, State], None]]] = {
    "F1": (f1_send, f1_check),
    "F3": (f3_send, f3_check),
    "F4": (f4_send, f4_check),
    "F5": (f5_send, f5_check),
}
FLOWS = ["F1", "F2", "F3", "F4", "F5", "F6"]


def answered(db: Emulator, flow: str, rid: str, seconds: float) -> bool:
    """Poll request ``rid`` for its result for up to ``seconds``."""
    print(f"{flow} wait: request {rid}, up to {seconds:.0f} s", flush=True)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if result := db.node(f"requests/{rid}/result"):
            print(f"  result={json.dumps(result)[:300]}", flush=True)
            return True
        time.sleep(1)
    return False


def phases(flow: Flow, args: argparse.Namespace) -> int:
    """Run ``args.phase`` of a phased flow (all three for ``all``)."""
    send, check = PHASED[args.flow]
    state_file = Path(args.state)
    if args.phase in {"send", "all"}:
        state_file.write_text(json.dumps(send(flow)))
    if args.phase in {"wait", "all"}:
        state = json.loads(state_file.read_text())
        while not answered(flow.db, args.flow, state["rid"], args.wait):
            if args.phase == "wait":
                print(f"PENDING {args.flow}: call wait again", flush=True)
                return PENDING
    if args.phase in {"check", "all"}:
        check(flow, json.loads(state_file.read_text()))
    return 0


def carry(flow: Flow, args: argparse.Namespace) -> None:
    """F6: ``check`` (or ``all``) saves the ledger; ``again`` compares it."""
    state_file = Path(args.state)
    if args.phase == "again":
        f6_again(flow, json.loads(state_file.read_text()))
    else:
        state_file.write_text(json.dumps(f6_check(flow)))


def drive(args: argparse.Namespace, browser: Browser | None) -> int:
    """Run ``args.flow`` (its ``args.phase``, or all of it); the exit code."""
    flow = Flow(args, browser)  # wait has no browser: it reads the emulator only
    try:
        if args.flow == "F6":
            carry(flow, args)
        elif args.flow not in PHASED:
            f2(flow)
        elif (code := phases(flow, args)) != 0:
            return code
    except (FlowError, CdpError, OSError, KeyError, TypeError, ValueError) as err:
        # The FAIL line is the verdict an agent greps for.
        _logger.warning("FAIL %s step %d: %s", args.flow, flow.n, err)
        if browser is not None:
            for problem in browser.problems[-10:]:
                print(f"  page {problem[:500]}", flush=True)
            flow.shot("fail")
        return 1
    if args.phase in {"check", "all", "again"} or args.flow not in PHASED:
        print(f"PASS {args.flow}", flush=True)
    else:
        print(f"OK {args.flow} {args.phase}", flush=True)
    return 0


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=FLOWS)
    parser.add_argument(
        "phase",
        nargs="?",
        default="all",
        choices=["send", "wait", "check", "again", "all"],
    )
    parser.add_argument("--app", required=True, help="http://127.0.0.1:N/app/")
    parser.add_argument("--db", required=True, help="emulator http://127.0.0.1:N")
    parser.add_argument("--card", required=True, help="the card that must start")
    parser.add_argument("--out", required=True, help="screenshot prefix")
    parser.add_argument("--state", required=True, help="send's state, for wait/check")
    parser.add_argument("--wait", type=float, default=45, help="wait: seconds per call")
    parser.add_argument("--data", type=Path, help="the sandbox data dir (ledger)")
    parser.add_argument("--session", help="F3/F4: the session at card end")
    parser.add_argument("--display", default=":97")
    # :97 is 4K, so the app's UI scale is 2: 2560x1440 lays out as 1280x720.
    parser.add_argument("--size", default="2560x1440", help="window WIDTHxHEIGHT")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    if args.phase == "wait":
        return drive(args, None)
    width, height = (int(n) for n in args.size.split("x"))
    log = Path(f"{args.out}_chrome.log")
    with Browser(args.display, log, (width, height)) as browser:
        return drive(args, browser)


if __name__ == "__main__":
    raise SystemExit(main())
