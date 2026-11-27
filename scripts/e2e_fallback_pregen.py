#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""F33's pre-draft phases (C10), on a plain ``up`` (Claude up, no outage).

* ``pregen`` (right after ``up``, before the worker's first round at 60 s)
  saves the targets: each subject studied in the last 7 days with its first
  locked, undrafted module (``pregen_auto.picks``), and each idle subject's.
* ``pregencheck`` (75 = again, while a target still drafts): every studied
  target has drafted cards and is still ``locked``; no idle subject's module
  got a card or a ``pregenerated`` mark. It screenshots the first target's
  Plan.
"""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from e2e_flow import FlowError

from tutor.curriculum import pregen_auto
from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from e2e_flow import Flow

PENDING: Final = 75


def _ctx(flow: Flow) -> Context:
    return Context(Path(flow.args.data), device="e2e")


def pregen(flow: Flow) -> int:
    """Save the studied targets and the idle subjects' undrafted modules."""
    ctx, now = _ctx(flow), int(time.time() * 1000)
    targets = pregen_auto.picks(ctx, now)
    active = pregen_auto.studied(ctx.log.read(), now)
    idle = []
    for subject in ctx.subjects.subjects():
        plan = ctx.subjects.plan(subject)
        if subject in active or plan is None:
            continue
        cards = ctx.subjects.cards(subject)
        if (found := pregen_auto.next_module(plan, cards)) is not None:
            idle.append((subject, found))
    flow.step(f"targets {targets}; idle {idle}")
    if not targets or not idle:
        msg = "the copy needs a studied and an idle subject with an undrafted module"
        raise FlowError(msg)
    state = {"targets": targets, "idle": idle}
    Path(flow.args.state).write_text(json.dumps(state), encoding="utf-8")
    return 0


def _module(ctx: Context, subject: str, module: str) -> tuple[str, bool, int]:
    """``(status, pregenerated, cards)`` of ``module``."""
    plan = ctx.subjects.plan(subject)
    found = next(m for m in (plan.modules if plan else []) if m.id == module)
    cards = sum(c.module == module for c in ctx.subjects.cards(subject).values())
    return found.status, bool(found.pregenerated), cards


def pregencheck(flow: Flow) -> int:
    """Studied targets drafted and locked; idle subjects untouched."""
    state = json.loads(Path(flow.args.state).read_text(encoding="utf-8"))
    ctx = _ctx(flow)
    seen = {f"{s}/{m}": _module(ctx, s, m) for s, m in state["targets"]}
    flow.note(f"targets {seen}")
    if any(status == "generating" or not n for status, _, n in seen.values()):
        return PENDING
    flow.step("every target is drafted and still locked")
    if any(status != "locked" for status, _, _ in seen.values()):
        msg = f"a pre-drafted module unlocked: {seen}"
        raise FlowError(msg)
    idle = {f"{s}/{m}": _module(ctx, s, m) for s, m in state["idle"]}
    flow.step(f"no idle subject got a draft: {idle}")
    if any(pre or n for _, pre, n in idle.values()):
        msg = f"an idle subject was drafted: {idle}"
        raise FlowError(msg)
    flow.screen(f"/plan/{state['targets'][0][0]}")
    time.sleep(4)
    flow.shot("pregen")
    return 0


PHASES: Final[dict[str, Any]] = {"pregen": pregen, "pregencheck": pregencheck}
