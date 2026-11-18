#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F18: archive a subject from Home, then undo it.

Runs on a fresh sandbox ``up`` (``e2e_sandbox.sh``), one call, model-free.
The subject is ``--subject`` when it has taught cards, else the first one
that does (none generating cards, so the build lane is free). The checks
read the sandbox copy (``--data``) and the emulator, never live data.

1. the subject is in the emulator catalog and has taught cards;
2. Home -> its delete glyph ("Archive <title>"): a ``subject_archive``
   request, answered ok; the row is gone from Home, ``subjects/<id>`` is gone
   from the emulator, the worker pushed the log event, and the sandbox fold
   counts none of its cards as taught;
3. the undo glyph ("Undo archive <title>", shown for 8 s): a
   ``subject_unarchive`` answered ok; the row, the catalog node and the very
   same taught set are back.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from e2e_flow import FlowError

from tutor.curriculum.context import Context

if TYPE_CHECKING:
    from e2e_flow import Flow


def _pick(flow: Flow, ctx: Context) -> tuple[str, set[str]]:
    """``--subject`` if it has taught cards, else the first that has."""
    flow.step("pick a subject with taught cards and no module generating")
    folded = ctx.fold()
    names = [flow.args.subject, *ctx.subjects.subjects()]
    for name in names:
        plan = ctx.subjects.plan(name) if name in ctx.subjects.subjects() else None
        busy = plan is None or any(m.status == "generating" for m in plan.modules)
        if not busy and (taught := folded.taught_ids(name)):
            flow.note(f"subject={name} taught={len(taught)}")
            return name, taught
    msg = f"no subject with taught cards among {names}"
    raise FlowError(msg)


def _ok(flow: Flow, kind: str, since: set[str]) -> None:
    result = flow.result(kind, since, timeout=20)
    if not result.get("ok"):
        msg = f"{kind} refused: {result}"
        raise FlowError(msg)


def _gone(flow: Flow, ctx: Context, subject: str, label: str) -> None:
    flow.step("archived: gone from Home, the catalog and the fold")
    if flow.db.get(f"subjects/{subject}") is not None:
        msg = f"subjects/{subject} is still in the emulator catalog"
        raise FlowError(msg)
    pushed = flow.db.node(f"log/{ctx.device}").values()
    if not any(
        e.get("k") == "subject_archive" and e.get("s") == subject for e in pushed
    ):
        msg = "the worker did not push its subject_archive event"
        raise FlowError(msg)
    if subject not in ctx.archived() or ctx.fold().taught_ids(subject):
        msg = f"{subject} still counts as learned in the sandbox fold"
        raise FlowError(msg)
    if flow.browser.find(label) is not None:
        msg = f"{label!r} is still on Home"
        raise FlowError(msg)
    flow.note("catalog node deleted, event pushed, 0 cards taught, row hidden")


def f18(flow: Flow) -> None:
    """Archive from Home, check it is gone and unlearned, undo, check it is back."""
    ctx = Context(flow.args.data)
    subject, taught = _pick(flow, ctx)
    meta = ctx.subjects.need_meta(subject)
    label, undo = f"Archive {meta.title}", f"Undo archive {meta.title}"
    if not flow.db.node(f"subjects/{subject}/meta"):
        msg = f"subjects/{subject} is not in the emulator catalog"
        raise FlowError(msg)
    flow.home()
    flow.expect(label, timeout=30)
    flow.shot("before")
    before = flow.rids()
    flow.tap(label)
    tapped = time.monotonic()
    _ok(flow, "subject_archive", before)
    _gone(flow, ctx, subject, label)
    flow.shot("archived")
    flow.note(f"undo tapped {time.monotonic() - tapped:.1f} s after the archive tap")
    before = flow.rids()
    flow.tap(undo, timeout=3)
    _ok(flow, "subject_unarchive", before)
    flow.step("restored: back on Home, in the catalog, same taught cards")
    if not flow.db.node(f"subjects/{subject}/meta"):
        msg = f"subjects/{subject} was not republished"
        raise FlowError(msg)
    if subject in ctx.archived() or ctx.fold().taught_ids(subject) != taught:
        msg = f"{subject}'s learning state did not come back"
        raise FlowError(msg)
    flow.expect(label, timeout=20)
    flow.note(f"taught={len(taught)} again; the row is back")
    flow.shot("restored")
