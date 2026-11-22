# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Support for the unrefuse repair tests: a refused-done session on a two-module subject."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests._phase import LC

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.source import CardSource

SID = "20261122-181138-58ac"
AT = "2026-11-22T17:16:37+00:00"  # the refused turn, as logged
LATER = "2026-11-22T18:00:00+00:00"
REFUSED = {"card_done": False, "card_done_refused": ["a0"], "message": "Passed."}


def engine_for(root: Path) -> Engine:
    """a refused (holds a0); b: b0, then b1 needing b0 and a0."""
    ctx, _ = make_ctx(root)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {"a0": card("a", 0), "b0": card("b", 0), "b1": card("b", 1, "b0", "a0")}
    subject(ctx, LC, modules=mods, found=found)
    return Engine(
        store=Store(root),
        now=ManualClock(),
        session_factory=lambda _: FakeSession(turn()),
    )


def src(engine: Engine) -> CardSource:
    return engine._source_for(LC)  # a fresh subject source, as the repair builds


def log(engine: Engine, sid: str, *events: dict[str, Any]) -> None:
    for event in events:
        engine.store.log(sid, event)


def refused_session(engine: Engine, sid: str = SID, card_id: str = "b1") -> None:
    log(
        engine,
        sid,
        {"type": "start", "card": card_id, "subject": LC},
        {"type": "tutor", "turn": {"message": "Hi", "card_done": False}},
        {"type": "learner", "text": "the answer"},
        {"type": "tutor", "turn": dict(REFUSED), "logged_at": AT},
    )


def flips(root: Path) -> list[tuple[str, bool]]:
    path = root / "module_state.json"
    rows = json.loads(path.read_text())["entries"] if path.exists() else []
    return [(r["detail"]["module"], r["detail"]["done"]) for r in rows]


def taught(engine: Engine) -> set[str]:
    return set(engine.ctx.fold().taught_ids(LC))


def transcript(root: Path, sid: str = SID) -> str:
    return (root / "sessions" / f"{sid}.jsonl").read_text()
