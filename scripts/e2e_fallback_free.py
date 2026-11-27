#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's free-chat phases (C9, the gateway up): ``free``, ``freewait``, ``freecheck``.

On a sandbox ``up --outage rate_limit --fallback read`` with OmniRoute up:

* ``free`` taps the outage banner's free-chat glyph and saves the
  ``session_start`` request id in the flow's ``--state`` file.
* ``freewait`` waits up to 30 s for its result; 75 while the free model's
  first turn is still pending (call it again).
* ``freecheck``: the start is ok, the live session has a tutor message, then
  "Mark card done" closes the card and the log gains a ``taught`` and an
  ``unchecked`` with ``src: free`` for it (spec Q9: weak teaching is checked).
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_fallback_checks import log_events
from e2e_flow import FlowError

if TYPE_CHECKING:
    from e2e_flow import Flow

PENDING: Final = 75
WAIT_S: Final = 30.0
FREE_CHAT: Final = "Free chat"
DONE: Final = "Mark card done"


def _state(flow: Flow) -> dict[str, Any]:
    path = Path(flow.args.state)
    if not path.is_file():
        msg = "no free-chat state: run `flow F33 free` first"
        raise FlowError(msg)
    return dict(json.loads(path.read_text(encoding="utf-8")))


def free(flow: Flow) -> int:
    """Tap the banner's free-chat glyph; save the ``session_start`` id."""
    flow.home()
    flow.expect(FREE_CHAT, timeout=30)
    before = flow.rids()
    since = int(time.time() * 1000)
    flow.tap(FREE_CHAT)
    rid = flow.request("session_start", before)
    body = (flow.db.node(f"requests/{rid}/req") or {}).get("body") or {}
    if not body.get("free"):
        msg = f"the free-chat glyph sent a non-free start: {json.dumps(body)[:200]}"
        raise FlowError(msg)
    state = {"rid": rid, "since": since}
    Path(flow.args.state).write_text(json.dumps(state), encoding="utf-8")
    return 0


def freewait(flow: Flow) -> int:
    """0 once the free start has a result; 75 while it is still pending."""
    rid = str(_state(flow)["rid"])
    flow.step(f"wait for session_start {rid}'s result")
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if found := flow.result_of(rid):
            flow.note(f"result={json.dumps(found)[:300]}")
            return 0
        time.sleep(1)
    return PENDING


def _free_marks(flow: Flow, card: str, since: int) -> list[str]:
    """The kinds logged for ``card`` at or after ``since`` (``unchecked:<src>``)."""
    kinds = []
    for event in log_events(flow.args.data):
        if event.get("c") == card and int(event.get("at", 0)) >= since:
            kind = str(event.get("k"))
            kinds.append(f"{kind}:{event['src']}" if "src" in event else kind)
    return kinds


def freecheck(flow: Flow) -> int:
    """The free tutor answered; its finished card is taught and unchecked."""
    state = _state(flow)
    flow.step("the free start is ok and the live session has a tutor message")
    result = flow.result_of(str(state["rid"]))
    if not result or result.get("code"):
        msg = f"free start failed: {json.dumps(result)[:300]}"
        raise FlowError(msg)
    live = flow.db.node("live")
    msgs = flow.db.node(f"sessions/{live.get('session')}/msgs")
    tutor = [m for _, m in sorted(msgs.items()) if m.get("role") == "tutor"]
    if not tutor:
        msg = f"live {live} has no tutor message"
        raise FlowError(msg)
    flow.note(f"card={live.get('card')} tutor: {str(tutor[0].get('text'))[:160]!r}")
    flow.screen("/session")
    time.sleep(3)
    flow.shot("free")
    before = flow.rids()
    flow.tap(DONE, timeout=30)
    if not flow.result("card_done", before, timeout=30).get("ok"):
        msg = "card_done refused"
        raise FlowError(msg)
    flow.step("the log has taught + unchecked:free for the finished card")
    kinds = _free_marks(flow, str(live.get("card")), int(state["since"]))
    flow.note(f"kinds={kinds}")
    if "taught" not in kinds or "unchecked:free" not in kinds:
        msg = f"want taught and unchecked:free, got {kinds}"
        raise FlowError(msg)
    return 0


PHASES: Final[dict[str, Any]] = {
    "free": free,
    "freewait": freewait,
    "freecheck": freecheck,
}
