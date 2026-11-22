# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A prerequisite in a module C3 refuses holds no done-gate shut either.

The picker (``pick._open``), the tutor's ``card_done`` (``phase_gate.blockers``)
and the manual mark (``Engine.set_card_done``) share one rule,
``gating.missing(..., waived)``. Live 2026-11-22: the picker offered
``histogram-prefix-sorted-position`` of ``prefix-sums`` but its ``card_done``
was refused over ``direct-index-counting-array`` of the refused ``hashing``,
so the module never read done.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests._phase import LC, SQL, grant

if TYPE_CHECKING:
    from pathlib import Path

DONE = {"card_done": True, "check_result": {"passed": True, "feedback": "yes"}}


def _engine(root: Path, fake: FakeSession, name: str = LC) -> Engine:
    """a refused (holds a0); b: b0, then b1 needing b0 and a0."""
    ctx, _ = make_ctx(root)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {"a0": card("a", 0), "b0": card("b", 0), "b1": card("b", 1, "b0", "a0")}
    subject(ctx, name, modules=mods, found=found)
    return Engine(store=Store(root), now=ManualClock(), session_factory=lambda _: fake)


def _flips(root: Path) -> list[tuple[str, bool]]:
    raw = json.loads((root / "module_state.json").read_text())
    return [(r["detail"]["module"], r["detail"]["done"]) for r in raw["entries"]]


def _tutor_turns(root: Path) -> list[dict[str, Any]]:
    path = max((root / "sessions").glob("*.jsonl"))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    return [e["turn"] for e in lines if e["type"] == "tutor"]


def test_a_card_whose_prerequisite_is_refused_is_taught_and_the_module_done(
    tmp_path: Path,
) -> None:
    grant((LC, "b"))  # THEORY(b); a is refused
    fake = FakeSession(turn(), turn("Done.", **DONE), turn(), turn("Done.", **DONE))
    engine = _engine(tmp_path, fake)
    assert asyncio.run(engine.start(subject=LC))["card"]["id"] == "b0"
    asyncio.run(engine.reply("the answer"))
    assert asyncio.run(engine.next_card())["card"]["id"] == "b1"
    state = asyncio.run(engine.reply("the answer"))
    assert state["card_done"]
    assert engine.ctx.fold().taught_ids(LC) == {"b0", "b1"}
    assert _flips(tmp_path) == [("b", True)]
    for logged in _tutor_turns(tmp_path):
        assert "card_done_refused" not in logged


def test_a_prerequisite_in_a_teachable_module_still_blocks_done(
    tmp_path: Path,
) -> None:
    grant((LC, "a"), (LC, "b"))
    engine = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(engine.start("a0", subject=LC))
    with pytest.raises(ValueError, match="locked until"):
        asyncio.run(engine.set_card_done("b1", done=True, subject=LC))


def test_the_manual_mark_follows_the_same_rule(tmp_path: Path) -> None:
    grant((LC, "b"))
    engine = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(engine.start(subject=LC))
    asyncio.run(engine.set_card_done("b0", done=True, subject=LC))
    asyncio.run(engine.set_card_done("b1", done=True, subject=LC))
    assert engine.ctx.fold().taught_ids(LC) == {"b0", "b1"}


def test_an_ungated_subject_keeps_every_prerequisite(tmp_path: Path) -> None:
    grant((LC, "b"))  # never read: SQL is not gated
    engine = _engine(tmp_path, FakeSession(turn()), SQL)
    asyncio.run(engine.start("a0", subject=SQL))
    with pytest.raises(ValueError, match="locked until"):
        asyncio.run(engine.set_card_done("b1", done=True, subject=SQL))
