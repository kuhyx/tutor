#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F11: unbacked timer minutes on the Focus screen.

Runs on a sandbox that is ``up`` (``e2e_sandbox.sh``) with focus_project >= 0.10.0
(``E2E_FOCUS_SRC``): its data dir is ``--focus``. Model-free; one call.

1. a project covering today is created through the relay;
2. a timer-only stretch (start 15 min ago, stop 5 min ago, no beat) is written
   as the app's timer would: the ring shows 0 and the line
   "10 min unbacked (not counted)" is on screen;
3. a ``tutor`` heartbeat inside the stretch (what a graded answer emits, with
   the answer's own time) is added: after a reload the ring shows the full 10
   and the unbacked line is gone.
"""

from __future__ import annotations

import json
from pathlib import Path
import time

from e2e_flow import Flow, FlowError
from e2e_focus import ROUTE, _activity, _create_project

PROJECT = "e2e-focus"
SPAN_MIN = 10


def _append(path: Path, source: str, kind: str, ts: float) -> None:
    row = {"ts": ts, "source": source, "kind": kind, "project": PROJECT, "dev": "pc"}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _absent(flow: Flow, text: str) -> None:
    """``text`` is not on screen (after the page settled)."""
    flow.step(f"not on screen: {text}")
    time.sleep(2)
    if text in flow.browser.page_text():
        msg = f"{text!r} is still shown: {flow.browser.page_text()[:300]!r}"
        raise FlowError(msg)


def f11(flow: Flow) -> None:
    """Timer-only stretch shows 0 + the unbacked line; a beat inside backs it."""
    activity = Path(flow.args.focus) / "activity.jsonl"
    flow.step(f"precondition: {activity} has no events")
    if _activity(activity):
        msg = "sandbox focus data is not fresh (run e2e_sandbox.sh up)"
        raise FlowError(msg)
    _create_project(flow)
    now = float(int(time.time()))
    flow.step("a timer-only stretch: start 15 min ago, stop 5 min ago")
    _append(activity, "timer", "start", now - 900)
    _append(activity, "timer", "stop", now - 300)
    line = f"{SPAN_MIN} min unbacked (not counted)"
    flow.screen(ROUTE)
    flow.expect("E2E focus", line)
    flow.shot("unbacked")
    flow.step("a tutor beat inside the stretch (an answer given 10 min ago)")
    _append(activity, "tutor", "heartbeat", now - 600)
    flow.screen(ROUTE)
    flow.expect("E2E focus", str(SPAN_MIN))
    _absent(flow, "unbacked")
    flow.shot("backed")
