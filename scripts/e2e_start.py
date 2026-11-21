#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flows F1 and F2: "Continue learning" starts the next card.

F1 runs in phases (``send`` here, ``check`` after the worker answered); F2
is one call at the daily cap. Run through ``e2e_drive.py``.
"""

from __future__ import annotations

import json

from e2e_flow import Flow, FlowError, State


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
