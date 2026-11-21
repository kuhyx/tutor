#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F20: a card's interrogation path reaches the tutor, unseen.

Runs on a fresh ``up`` (no ``--as-of``) with ``E2E_SUBJECT`` set for ``up``
and every phase. The draft tier writes a path per
card (``tutor.curriculum.paths``); the tutor reads it before its first
question and the learner never sees it.

* send: a path is planted on every live card of ``E2E_SUBJECT`` (pick one
  with a card never taught and no live session: an opening about a
  lighthouse keeper, no typed follow-up, a pass criterion holding a marker
  word), then Home -> "Continue learning".
* check (after ``wait``): the session started (or resumed), the server log
  says its tutor prompt carried the path (``prompt.for_source``; what the
  model then asks is its own choice: the path is a suggestion), and neither the
  session screen nor the published card holds the marker or the path.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

from e2e_flow import Flow, FlowError, State

from tutor.curriculum import paths
from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from collections.abc import Callable

MARKER: Final = "criterion-zebra"
OPENING: Final = (
    "A lighthouse keeper who has never heard of this topic asks you about it "
    "over the radio. Before anything else: what would you tell the keeper "
    "this card is about?"
)
PATH: Final = {
    "opening": OPENING,
    "probes": ["What would the keeper get wrong without your explanation?"],
    "misconception": "",
    "correction": "",
    "hints": ["Start from what the keeper can see from the tower."],
    "tell": [],
    "pass_criterion": f"States the card's answer in their own words. {MARKER}",
    "typed_follow_up": False,
}


def f20_send(flow: Flow, start: Callable[[Flow], State]) -> State:
    """Plant the path on every live card of the subject, then ``start`` (F1)."""
    subject = str(flow.args.subject)
    ctx = Context(flow.args.data)
    live = {c: r for c, r in ctx.subjects.cards(subject).items() if not r.suspended}
    flow.step(f"plant an interrogation path on {len(live)} cards of {subject}")
    path = paths.clean(PATH)
    paths.save(ctx, subject, {cid: (rec.rev, path) for cid, rec in live.items()})
    return {**start(flow), "subject": subject}


def f20_check(flow: Flow, state: State, started: Callable[[Flow, State], None]) -> None:
    """``started`` (F1's check) holds, the first turn follows the path, unseen."""
    live = flow.db.node("live")
    card_id = str(live.get("card"))
    flow.args.card = card_id  # any card of the subject will do: all carry the path
    started(flow, state)
    if live.get("subject") != state["subject"]:
        msg = f"the session is not on {state['subject']}: live={live}"
        raise FlowError(msg)
    flow.step("the server log says the tutor prompt carried the path")
    want = f"tutor prompt for {state['subject']}/{card_id}: interrogation path given"
    log = (flow.args.data.parent / "server.log").read_text(encoding="utf-8")
    if want not in log:
        seen = [line for line in log.splitlines() if "interrogation path" in line]
        msg = f"no {want!r} in server.log; saw {seen[-3:]}"
        raise FlowError(msg)
    flow.step("the path is neither on screen nor in the published card")
    shown = flow.browser.page_text()
    card = flow.db.node(f"subjects/{state['subject']}/cards/{card_id}")
    hidden = MARKER not in shown and "interrogation path" not in shown
    if not hidden or MARKER in json.dumps(card) or "path" in card:
        msg = f"the path leaked: screen={MARKER in shown} card keys={sorted(card)}"
        raise FlowError(msg)
    flow.shot("path_hidden")
