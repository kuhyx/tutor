# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's ``mnemonic`` and ``split`` card edits, applied after its turn."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor import edit_flow
from tutor.card_requests import CardEdit, SplitPart
from tutor.curriculum import card_ops, card_rules
from tutor.tests._fakes import FakeSession, turn
from tutor.tests.test_card_ops import BACK, FRONT, PISTON, car_subject
from tutor.tests.test_card_split import KIND_B, KIND_F
from tutor.tests.test_engine_card_edits import _car, _engine

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

INTO = (
    SplitPart(KIND_F, KIND_B, PISTON, "component of reciprocating engines"),
    SplitPart(FRONT, BACK, PISTON),
)


def test_a_mnemonic_on_the_live_card_then_cleared(tmp_path: Path) -> None:
    ctx, _ = car_subject(tmp_path)
    aid = CardEdit("mnemonic", text="Thing one: the first thing.")
    done = edit_flow.apply_edits(ctx, "car", "a1", (aid,))
    assert done.notices == ["Mnemonic set: What is thing 1 of a?"]
    assert ctx.subjects.cards("car")["a1"].mnemonic == "Thing one: the first thing."
    done = edit_flow.apply_edits(ctx, "car", "a1", (CardEdit("mnemonic", card="a1"),))
    assert done.notices == ["Mnemonic cleared: What is thing 1 of a?"]
    assert done.removed_live == ""


def test_splitting_the_live_card_leaves_it(tmp_path: Path) -> None:
    ctx, _ = car_subject(tmp_path)
    other = edit_flow.apply_edits(
        ctx, "car", "a1", (CardEdit("split", card="a2", into=INTO),)
    )
    assert other.notices == ["Card split into 2: What is thing 2 of a?"]
    assert other.removed_live == ""
    live = edit_flow.apply_edits(ctx, "car", "a1", (CardEdit("split", into=INTO[:1]),))
    assert live.refusals == ["split a1: a split makes 2-4 cards, not 1"]
    assert not ctx.subjects.cards("car")["a1"].suspended


def test_the_session_moves_on_to_the_first_half(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _car(tmp_path)
    monkeypatch.setattr(card_rules, "source_problem", lambda *_a: None)
    excerpt = "a piston is a component of reciprocating engines in cars"
    monkeypatch.setattr(card_ops, "quoted", lambda *_a: excerpt)
    split = CardEdit("split", into=INTO)
    fake = FakeSession(
        turn("What do you remember of thing 0?"),
        turn("I split it in two.", card_edits=(split,)),
        turn("First half: what kind of engine has a piston?"),
    )
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start(subject="car"))
    asyncio.run(engine.reply("split it please"))
    cards = engine.ctx.subjects.cards("car")
    assert cards["c0"].suspended
    assert engine.card is not None
    assert engine.card.id == "what-kind-of-engine-has-a-piston"
    assert cards[engine.card.id].split_of == "c0"
    assert engine.messages[0]["notices"] == ["Card split into 2: What is thing 0 of a?"]
