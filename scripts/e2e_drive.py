#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows: tap the real web build, assert on the emulator, screenshot.

Run by ``scripts/e2e_sandbox.sh flow <F1|F3|...|F21> [send|wait|check]``
against a sandbox that is ``up``. Every step is printed before it runs, so on
failure the last line names it; a failure also saves ``<out>_fail.png``.
Exit 0 = PASS.

* F1 Continue learning (``e2e_start.py``): Home -> "Continue
  learning" -> the subject's next card (``--card``) is live and its first
  tutor message is on screen. (F2, the daily cap, went with the cap.)
* F3, F4 follow-up questions (``e2e_follow_up.py``).
* F5 help on a struggling card (``e2e_struggle.py``; phased like F1).
* F6 the carry-over bank (``e2e_carry.py``): ``check``, then ``again`` after
  ``e2e_sandbox.sh restart``.
* F7-F19, one module each: ``e2e_focus`` (F7, F8), ``e2e_checkin`` (F9,
  F10), ``e2e_unbacked`` (F11), ``e2e_blocked`` (F12), ``e2e_codes`` (F13),
  ``e2e_failures`` (F14), ``e2e_interview`` (F15), ``e2e_glyphs`` (F16),
  ``e2e_keyless`` (F17), ``e2e_split`` (F18), ``e2e_archive`` (F19),
  ``e2e_path`` (F20), ``e2e_gate`` (F21, phased; ``up --gate``).
* F22 a ``#/learn/S/M`` route teaches the module, pays C1 and flips C2
  (``e2e_learn.py``, seven phases); F26 the window takeover
  (``e2e_takeover.py``).

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

from e2e_archive import f19
from e2e_blocked import f12
from e2e_carry import f6_again, f6_check
from e2e_cdp import Browser, CdpError
from e2e_checkin import f9, f10
from e2e_codes import OUTAGES, f13
from e2e_composer_glyphs import again as f21_again
from e2e_failures import PHASES as F14_PHASES
from e2e_failures import f14
from e2e_flow import Emulator, Flow, FlowError, State
from e2e_focus import f7, f8
from e2e_follow_up import f3_check, f3_send, f4_check, f4_send
from e2e_gate import f21_check, f21_send
from e2e_glyphs import PHASES as F16_PHASES
from e2e_glyphs import f16
from e2e_interview import f15
from e2e_keyless import f17
from e2e_learn import F21_PHASES, f21
from e2e_path import f20_check, f20_send
from e2e_split import f18_check, f18_send
from e2e_start import f1_check, f1_send
from e2e_struggle import f5_check, f5_send
from e2e_takeover import LC, AppBrowser, f25
from e2e_unbacked import f11

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)
PENDING = 75  # wait: the worker has not answered yet; call wait again


PHASED: dict[str, tuple[Callable[[Flow], State], Callable[[Flow, State], None]]] = {
    "F1": (f1_send, f1_check),
    "F3": (f3_send, f3_check),
    "F4": (f4_send, f4_check),
    "F5": (f5_send, f5_check),
    "F18": (f18_send, f18_check),
    "F21": (f21_send, f21_check),
    "F20": (
        lambda flow: f20_send(flow, f1_send),
        lambda flow, state: f20_check(flow, state, f1_check),
    ),
}
FLOWS = ["F1", *(f"F{n}" for n in range(3, 27))]  # F2 (the cap) is gone
ONE_CALL: dict[str, Callable[[Flow], None]] = {
    "F7": f7,
    "F8": f8,
    "F9": f9,
    "F10": f10,
    "F11": f11,
    "F12": f12,
    "F13": f13,
    "F14": f14,
    "F15": f15,
    "F16": f16,
    "F17": f17,
    "F19": f19,
    "F26": f25,
}


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


def carry(flow: Flow, args: argparse.Namespace) -> int:
    """F6: ``check`` (or ``all``) saves the ledger; ``again`` compares it."""
    state_file = Path(args.state)
    if args.phase == "again":
        f6_again(flow, json.loads(state_file.read_text()))
    else:
        state_file.write_text(json.dumps(f6_check(flow)))
    return 0


# Flows that keep their own state between calls; the exit code (75: again).
STATEFUL: dict[str, Callable[[Flow, argparse.Namespace], int]] = {
    "F6": carry,
    "F22": lambda flow, args: f21(flow, args.phase, Path(args.state)),
}


def drive(args: argparse.Namespace, browser: Browser | None) -> int:
    """Run ``args.flow`` (its ``args.phase``, or all of it); the exit code."""
    flow = Flow(args, browser)  # wait has no browser: it reads the emulator only
    try:
        if args.flow == "F21" and args.phase == "again":
            # After check: Send, once the in-box bulb's hint is answered.
            if (code := f21_again(flow)) != 0:
                return code
        elif args.flow in STATEFUL:
            if (code := STATEFUL[args.flow](flow, args)) != 0:
                return code
        elif args.flow in ONE_CALL:
            ONE_CALL[args.flow](flow)
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
    terminal = {"check"} if args.flow == "F22" else {"check", "all", "again"}
    if args.phase in terminal or args.flow not in {*PHASED, "F22"}:
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
        # F13 also takes one outage reason per call (each fits under 60 s).
        choices=[
            "send",
            "wait",
            "check",
            "again",
            "all",
            *OUTAGES,
            *F14_PHASES,
            *F16_PHASES,
            *F21_PHASES,
        ],
    )
    parser.add_argument("--app", required=True, help="http://127.0.0.1:N/app/")
    parser.add_argument("--db", required=True, help="emulator http://127.0.0.1:N")
    parser.add_argument("--card", required=True, help="the card that must start")
    parser.add_argument("--out", required=True, help="screenshot prefix")
    parser.add_argument("--state", required=True, help="send's state, for wait/check")
    parser.add_argument("--wait", type=float, default=45, help="wait: seconds per call")
    parser.add_argument("--data", type=Path, help="the sandbox data dir (ledger)")
    parser.add_argument("--focus", type=Path, help="F7: the sandbox focus_project dir")
    parser.add_argument("--session", help="F3/F4: the session at card end")
    parser.add_argument("--subject", help="F9/F10: the focus project's subject")
    parser.add_argument("--display", default=":97")
    # :97 is 4K, so the app's UI scale is 2: 2560x1440 lays out as 1280x720.
    parser.add_argument("--size", default="2560x1440", help="window WIDTHxHEIGHT")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    if args.phase == "wait":
        return drive(args, None)
    width, height = (int(n) for n in args.size.split("x"))
    log = Path(f"{args.out}_chrome.log")
    if args.flow == "F26":  # a real --app window on the plan (e2e_takeover.py)
        plan = f"{args.app}?db={args.db}#/plan/{LC}"
        with AppBrowser(args.display, log, (width, height), app=plan) as app:
            return drive(args, app)
    with Browser(args.display, log, (width, height)) as browser:
        return drive(args, browser)


if __name__ == "__main__":
    raise SystemExit(main())
