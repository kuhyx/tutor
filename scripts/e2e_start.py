#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F1: "Continue learning" starts the next card.

F1 runs in phases (``send`` here, ``check`` after the worker answered).
Run through ``e2e_drive.py``. (F2, the daily cap, is gone with the cap.)
"""

from __future__ import annotations

import json

from e2e_flow import Flow, FlowError, State


def f1_send(flow: Flow) -> State:
    """Home -> Continue learning: the session_start request is sent."""
    flow.precheck()
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
