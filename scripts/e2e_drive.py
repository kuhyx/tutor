#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows: tap the real web build, assert on the emulator, screenshot.

Run by ``scripts/e2e_sandbox.sh flow <F1|F2|F3|F4>`` against a sandbox that is
``up``. Every step is printed before it runs, so on failure the last line
names it; a failure also saves ``<out>_fail.png``. Exit 0 = PASS.

* F1 Continue learning: Home -> "Continue learning" -> the subject's next
  card (``--card``) is live and its first tutor message is on screen.
* F2 daily cap (sandbox ``up --new-cap N``, N <= today's new cards): the
  same tap ends on the blocked panel with "Learn more anyway"; tapping it
  starts ``--card`` with a tutor message.
* F3, F4 follow-up questions (``e2e_follow_up.py``).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from e2e_cdp import Browser, CdpError
from e2e_flow import Flow, FlowError
from e2e_follow_up import f3, f4

_logger = logging.getLogger(__name__)


def f1(flow: Flow) -> None:
    """Continue learning starts the next card with a tutor message."""
    flow.precheck(capped=False)
    flow.home()
    before = flow.rids()
    flow.tap("Continue learning", timeout=30)
    result = flow.start_result(before)
    if not result.get("ok"):
        flow.shot("blocked")
        msg = f"session_start refused: {result.get('code')}: {result.get('error')}"
        raise FlowError(msg)
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


FLOWS = {"F1": f1, "F2": f2, "F3": f3, "F4": f4}


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=sorted(FLOWS))
    parser.add_argument("--app", required=True, help="http://127.0.0.1:N/app/")
    parser.add_argument("--db", required=True, help="emulator http://127.0.0.1:N")
    parser.add_argument("--card", required=True, help="the card that must start")
    parser.add_argument("--out", required=True, help="screenshot prefix")
    parser.add_argument("--data", type=Path, help="the sandbox data dir (ledger)")
    parser.add_argument("--session", help="F3/F4: the session at card end")
    parser.add_argument("--display", default=":97")
    # :97 is 4K, so the app's UI scale is 2: 2560x1440 lays out as 1280x720.
    parser.add_argument("--size", default="2560x1440", help="window WIDTHxHEIGHT")
    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, format="%(message)s", level=logging.INFO)
    width, height = (int(n) for n in args.size.split("x"))
    log = Path(f"{args.out}_chrome.log")
    with Browser(args.display, log, (width, height)) as browser:
        flow = Flow(args, browser)
        try:
            FLOWS[args.flow](flow)
        except (FlowError, CdpError, OSError, KeyError, TypeError, ValueError) as err:
            # The FAIL line is the verdict an agent greps for.
            _logger.warning("FAIL %s step %d: %s", args.flow, flow.n, err)
            for problem in browser.problems[-10:]:
                print(f"  page {problem[:500]}", flush=True)
            flow.shot("fail")
            return 1
    print(f"PASS {args.flow}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
