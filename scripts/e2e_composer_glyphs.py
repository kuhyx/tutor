#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E F21's session checks: flag, in-box hint bulb, Send.

On the session the gate let through (kuhy, 2026-11-22), the tutor bubble's
flag opens the report dialog, the bulb inside the answer box sends "Hint",
and (``again``, once the hint's reply is in) a typed answer goes out with
Send.

``glyphs`` runs at the end of ``f21_check`` and saves the hint's request id
in the flow's state file; ``again`` waits up to 40 s for its reply (75 =
still pending: call ``again`` again), then sends.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import TYPE_CHECKING

from e2e_flow import FlowError

if TYPE_CHECKING:
    from e2e_flow import Flow, State

PENDING = 75  # the hint's reply is not in yet
COMPOSER = "Your answer"  # the answer box's spoken label (prefix)


def _body(flow: Flow, rid: str) -> dict[str, object]:
    return dict((flow.db.node(f"requests/{rid}/req") or {}).get("body") or {})


def glyphs(flow: Flow, state: State) -> None:
    """Flag -> report dialog (Cancel); in-box bulb -> a "Hint" message."""
    flow.tap("⚑ Report")
    flow.expect("About a tutor message", "Save report")
    flow.shot("report")
    flow.tap("Cancel")
    before = flow.rids()
    flow.tap("Hint")
    rid = flow.request("message", before)
    flow.step('its text is "Hint"')
    if (text := _body(flow, rid).get("text")) != "Hint":
        msg = f"the bulb sent {text!r}"
        raise FlowError(msg)
    Path(flow.args.state).write_text(json.dumps({**state, "hint": rid}))


def again(flow: Flow) -> int:
    """After the hint's reply: type an answer, Send, and see it go out."""
    state = json.loads(Path(flow.args.state).read_text())
    rid = str(state["hint"])
    flow.step(f"the hint's reply is in (request {rid})")
    deadline = time.monotonic() + 40
    while not flow.result_of(rid):
        if time.monotonic() > deadline:
            sys.stdout.write("PENDING F21 again: call it again\n")
            return PENDING
        time.sleep(1)
    flow.screen("/session")
    flow.expect("Send", timeout=20)
    flow.type_into(COMPOSER, "I think it is the power stroke.")
    before = flow.rids()
    flow.tap("Send")
    sent = flow.request("message", before)
    flow.step("Send carried the typed answer")
    if "the power stroke" not in str(_body(flow, sent).get("text")):
        msg = f"Send sent {_body(flow, sent)!r}"
        raise FlowError(msg)
    flow.shot("sent")
    return 0
