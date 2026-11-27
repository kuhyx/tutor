#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's gate phase (``e2e_fallback.py``; C7), on ``up --fallback gate``.

The seed leaves S's module M two untaught cards short of the gate before
S's next, unstarted module N (``e2e_fallback_seed.py`` ``gate``). ``gate``
reads those two in read mode (``#/read/S``, no outage), Got it and Again;
the server's own pick then refuses N with exactly them as ``gate_cards``
and ``gate_unchecked``.

The pick is ``pick.pick`` with no card: what a free session or an explicit
card in N meets. Home's Continue is never tapped: with the outage closed it
opens a Claude session that checks an unchecked card first (spec Q10,
``SubjectSource.pick``), a real model turn, and never shows the refusal.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_fallback_steps import dwell, flip, rate, shown_card
from e2e_flow import FlowError

from tutor.curriculum import rules
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.curriculum.pick import pick

if TYPE_CHECKING:
    from e2e_flow import Flow

_logger = logging.getLogger(__name__)


def _seed(flow: Flow) -> dict[str, Any]:
    path = Path(flow.args.data).parent / "f33_seed.json"
    return dict(json.loads(path.read_text(encoding="utf-8")))


def seeded_read(flow: Flow) -> list[str]:
    """The cards the ``gate`` seed leaves for read mode, sorted."""
    return sorted(_seed(flow)["read"])


def refusal(data: Path, subject: str) -> dict[str, Any]:
    """The extra of the server's own pick refusing S's next card (``{}``: none)."""
    ctx = Context(data, device="e2e")
    plan = ctx.subjects.plan(subject)
    if plan is None:
        return {}
    view = rules.View(subject, plan, ctx.subjects.cards(subject))
    try:
        pick(view, ctx.fold(), None, int(time.time() * 1000))
    except RequestError as err:
        _logger.warning("the pick refuses %s: %s", subject, err.code)
        return dict(err.extra)
    return {}


def held(flow: Flow, want: list[str]) -> None:
    """The pick refuses S's next module with exactly ``want``, all unchecked."""
    flow.step(f"the server's own pick holds the gate on {want}, unchecked")
    extra = refusal(Path(flow.args.data), flow.args.subject)
    flow.note(f"refusal={json.dumps(extra)[:300]}")
    cards = sorted(extra.get("gate_cards") or [])
    if cards != want or sorted(extra.get("gate_unchecked") or []) != want:
        msg = f"the pick would not hold on {want}: {extra}"
        raise FlowError(msg)


def gate(flow: Flow) -> None:
    """C7: two cards read without Claude hold the next module's gate."""
    want = seeded_read(flow)
    flow.screen(f"/read/{flow.args.subject}")
    before, read = flow.rids(), list[str]()
    for label in ("Got it", "Again"):
        card = shown_card(flow, before, set(read))
        read.append(card["id"])
        flip(flow)
        dwell(flow, 4)
        rate(flow, label)
    flow.step(f"the two read cards are the seeded ones: {want}")
    if sorted(read) != want:
        msg = f"read {read}, want {want}"
        raise FlowError(msg)
    held(flow, want)
    flow.shot("gate")


PHASES: Final[dict[str, Any]] = {"gate": gate}
