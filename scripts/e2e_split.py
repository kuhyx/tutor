#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F18: the learner asks for a split; the session moves on.

Runs on a sandbox with a live session (``up`` without ``--as-of``: a faked
clock breaks the model call; or after F1 on a fresh
card). Live 2026-11-18 a split the tutor asked for was refused by code (a
two-word quote hint could never match three words), the chat said the app
would move on, and the screen stayed on the old card.

* send: the live session's composer gets "split this card in two" and Send.
* check (after ``wait``; two model turns can outlast 60 s): the reply is ok,
  the transcript holds the split's ``next_card``, ``live.card`` is a NEW card
  whose ``split_of`` is the old one, the old card is suspended, and the
  session screen shows the composer on the next card.
"""

from __future__ import annotations

import json
from typing import Any

from e2e_flow import Flow, FlowError, State
from e2e_follow_up import COMPOSER, _events

from tutor.curriculum.context import Context

ASK = (
    "Split this card into two cards now, one per idea, each front asking for "
    "the exact term. Do not ask me anything first; apply the split."
)


def f18_send(flow: Flow) -> State:
    """Type the split request into the live session and Send."""
    flow.step("precondition: a live session on a card, not done")
    live = flow.db.node("live")
    sid, card = live.get("session"), live.get("card")
    if not sid or not card or flow.db.node(f"sessions/{sid}/meta").get("card_done"):
        msg = f"run F1 first; live={live}"
        raise FlowError(msg)
    count = len(flow.db.node(f"sessions/{sid}/msgs"))
    flow.screen("/session")
    since = flow.rids()
    flow.type_into(COMPOSER, ASK)
    flow.tap("Send")
    rid = flow.request("message", since)
    return {"sid": sid, "old": card, "count": count, "rid": rid}


def _moved_to(flow: Flow, sid: str, old: str) -> str:
    """The card the transcript's ``next_card`` moved to (else a FlowError)."""
    flow.step("the transcript holds the split's next_card")
    events = _events(flow.args.data, sid)
    moved = [e for e in events if e.get("type") == "next_card"]
    if not moved:
        notes = [str(e.get("note"))[:300] for e in events if "refused" in str(e)]
        msg = f"no next_card: the split did not move on ({notes})"
        raise FlowError(msg)
    new = str(moved[-1]["card"])
    if new == old:
        msg = f"next_card is the old card {old}"
        raise FlowError(msg)
    return new


def f18_check(flow: Flow, state: State) -> None:
    """The session is on the split's first half, and the screen shows it."""
    sid, old = str(state["sid"]), str(state["old"])
    flow.step("the message result is ok")
    result: dict[str, Any] = flow.result_of(str(state["rid"]))
    flow.note(f"result={json.dumps(result)[:300]}")
    if not result.get("ok"):
        msg = f"reply refused: {result}"
        raise FlowError(msg)
    new = _moved_to(flow, sid, old)
    live = flow.db.node("live")
    flow.step(f"live.card moved from {old} to {new}")
    if live.get("card") != new or live.get("session") == sid:
        msg = f"live={live}, want card {new} in a new session"
        raise FlowError(msg)
    subject = str(_events(flow.args.data, sid)[0]["subject"])
    cards = Context(flow.args.data).subjects.cards(subject)
    if not cards[old].suspended or cards[new].split_of != old:
        msg = f"{old} suspended={cards[old].suspended}; {new} of {cards[new].split_of}"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect("Send", timeout=30)
    flow.shot("moved_on")
