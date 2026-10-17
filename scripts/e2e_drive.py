#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows: tap the real web build, assert on the emulator, screenshot.

Run by ``scripts/e2e_sandbox.sh flow <F1|F2>`` against a sandbox that is
``up``. Every step is printed before it runs, so on failure the last line
names it; a failure also saves ``<out>_fail.png``. Exit 0 = PASS.

* F1 Continue learning: Home -> "Continue learning" -> the subject's next
  card (``--card``) is live and its first tutor message is on screen.
* F2 daily cap (sandbox ``up --new-cap N``, N <= today's new cards): the
  same tap ends on the blocked panel with "Learn more anyway"; tapping it
  starts ``--card`` with a tutor message.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any
import urllib.request

from e2e_cdp import Browser, CdpError

_logger = logging.getLogger(__name__)
# Call-to-action labels of the session screen's blocked panel.
BLOCKED_CTAS = ("Learn more anyway", "Review this subject")


class FlowError(RuntimeError):
    """A flow step saw something other than what it expects."""


class Emulator:
    """Read-only REST view of the sandbox RTDB (``/tutor/v1``)."""

    def __init__(self, url: str) -> None:
        """Bind the emulator base URL (``http://127.0.0.1:N``)."""
        self.url = url.rstrip("/")

    def get(self, path: str) -> object:
        """The JSON at ``path`` (``None`` if absent)."""
        with urllib.request.urlopen(
            f"{self.url}/tutor/v1/{path}.json", timeout=10
        ) as r:
            value: object = json.load(r)
            return value

    def node(self, path: str) -> dict[str, Any]:
        """The object at ``path``; ``{}`` when absent or not an object."""
        value = self.get(path)
        return value if isinstance(value, dict) else {}


class Flow:
    """Shared steps; ``step`` logs before each one runs."""

    def __init__(self, args: argparse.Namespace, browser: Browser) -> None:
        """Keep the run's arguments, browser and emulator."""
        self.args, self.browser, self.db = args, browser, Emulator(args.db)
        self.n = 0

    def step(self, what: str) -> None:
        """Print the next step's number and goal."""
        self.n += 1
        print(f"{self.args.flow} step {self.n}: {what}", flush=True)

    def shot(self, suffix: str) -> Path:
        """Save a screenshot as ``<out>_<suffix>.png`` and print its path."""
        out = self.browser.screenshot(Path(f"{self.args.out}_{suffix}.png"))
        print(f"{self.args.flow} screenshot: {out}", flush=True)
        return out

    def tap(self, label: str, timeout: float = 20) -> None:
        """Wait for the node labelled ``label``, scroll it on screen, click it."""
        self.step(f'tap "{label}"')
        hit = self.browser.wait_for(label, timeout)
        for _ in range(5):
            if hit is None or hit["visible"]:
                break
            self.browser.scroll(300 if hit["below"] else -300)
            time.sleep(0.5)
            hit = self.browser.find(label)
        if hit is None or not hit["visible"]:
            msg = f'no "{label}" on screen; saw: {self.browser.page_text()[:400]!r}'
            raise FlowError(msg)
        self.browser.click(hit)

    def precheck(self, *, capped: bool) -> None:
        """Today's new count vs the effective cap, as the worker published it."""
        self.step("precondition: stats.today and prefs from the emulator")
        today = self.db.node("stats").get("today") or {}
        prefs = self.db.node("prefs")
        new, cap = today.get("new"), today.get("new_cap")
        print(
            f"  today.new={new} new_cap={cap} prefs={prefs} live={self.db.get('live')}"
        )
        if not isinstance(new, int) or not isinstance(cap, int):
            msg = "stats.today has no new / new_cap (worker not up?)"
            raise FlowError(msg)
        if capped != (new >= cap):
            want = "new >= cap" if capped else "new < cap"
            msg = f"PRECONDITION: want {want}, have new={new} cap={cap}"
            raise FlowError(msg)

    def start_result(self, since: set[str], timeout: float = 45) -> dict[str, Any]:
        """The first new ``session_start`` request's result."""
        self.step("wait for the worker's session_start result")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for rid, node in sorted(self.db.node("requests").items()):
                req = node.get("req") or {}
                if rid in since or req.get("kind") != "session_start":
                    continue
                if result := node.get("result"):
                    shown = json.dumps(result)[:300]
                    print(f"  rid={rid} body={req.get('body')} result={shown}")
                    return dict(result)
            time.sleep(0.5)
        msg = f"no session_start result in {timeout:.0f} s"
        raise FlowError(msg)

    def rids(self) -> set[str]:
        """Request ids present now."""
        return set(self.db.node("requests"))

    def expect_card(self) -> None:
        """``live.card`` is ``--card`` and its first tutor message is on screen."""
        self.step(f"live card is {self.args.card} with a tutor message")
        live = self.db.node("live")
        if live.get("card") != self.args.card:
            msg = f"live={live}, want card {self.args.card}"
            raise FlowError(msg)
        msgs = self.db.node(f"sessions/{live['session']}/msgs")
        tutor = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"]
        if not tutor:
            msg = f"session {live['session']} has no tutor message"
            raise FlowError(msg)
        line = str(tutor[0].get("text", "")).strip().splitlines()[0]
        print(f"  session={live['session']} first tutor line: {line[:160]}")
        # Message bodies are selectable markdown with no semantics label, so
        # the screen check is: the composer is up and no blocked panel shows.
        self.step("the session screen is open with no blocked panel")
        if self.browser.wait_for("Send", 15) is None:
            msg = f"no composer; saw: {self.browser.page_text()[:400]!r}"
            raise FlowError(msg)
        time.sleep(2)
        if hits := [b for b in BLOCKED_CTAS if b in self.browser.page_text()]:
            msg = f"blocked panel still shown: {hits}"
            raise FlowError(msg)

    def home(self) -> None:
        """Open the app on Home."""
        self.step(f"open {self.args.app}")
        self.browser.open(f"{self.args.app}?db={self.args.db}")


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


FLOWS = {"F1": f1, "F2": f2}


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=sorted(FLOWS))
    parser.add_argument("--app", required=True, help="http://127.0.0.1:N/app/")
    parser.add_argument("--db", required=True, help="emulator http://127.0.0.1:N")
    parser.add_argument("--card", required=True, help="the card that must start")
    parser.add_argument("--out", required=True, help="screenshot prefix")
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
