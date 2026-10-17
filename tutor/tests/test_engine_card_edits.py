# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor edits cards mid-session: applied at once, a notice in the chat."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from tutor import edit_flow, resume
from tutor.card_requests import CardEdit
from tutor.curriculum import card_rules
from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import T0, card, make_ctx, module, subject, taught
from tutor.tests._fakes import FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

CLOCK_S = T0 / 1000
REMOVE = CardEdit("remove", reason="the learner says it is bad")


def _engine(root: Path, fake: FakeSession) -> Engine:
    return Engine(
        store=Store(root), now=ManualClock(CLOCK_S), session_factory=lambda _p: fake
    )


def _car(root: Path, n: int = 5) -> None:
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(n)}
    subject(ctx, modules=[module("a", status="ready", cards=n)], found=found)


def _events(root: Path, sid: str) -> list[dict[str, Any]]:
    path = root / "sessions" / f"{sid}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_learner_asks_to_remove_the_card(tmp_path: Path) -> None:
    _car(tmp_path)
    fake = FakeSession(
        turn("What do you know about thing 0?"),
        turn("Fair point, I removed that card.", card_edits=(REMOVE,)),
        turn("Next one: what do you know about thing 1?"),
    )
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start(subject="car"))
    first = engine.session_id
    asyncio.run(engine.reply("this card is bad, remove it"))

    cards = engine.ctx.subjects.cards("car")
    assert cards["c0"].suspended
    assert not any(c.suspended for cid, c in cards.items() if cid != "c0")
    assert engine.card is not None
    assert engine.card.id == "c1"
    assert engine.session_id != first
    notice = ["Card removed: What is thing 0 of a?"]
    old = _events(tmp_path, first)
    assert [e["type"] for e in old][-2:] == ["next_card", "stop"]
    assert old[-3]["ui"]["notices"] == notice
    assert engine.messages[0]["notices"] == notice
    replayed = resume.replay(tmp_path / "sessions" / f"{first}.jsonl")
    assert replayed is not None
    assert replayed.conversation.messages[-1]["notices"] == notice


def test_a_refused_edit_is_told_to_the_tutor(tmp_path: Path) -> None:
    _car(tmp_path, n=3)
    fake = FakeSession(
        turn(), turn("Removing it.", card_edits=(REMOVE,)), turn("Understood.")
    )
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start(subject="car"))
    sid = engine.session_id
    asyncio.run(engine.reply("remove it"))
    asyncio.run(engine.reply("ok?"))
    assert engine.session_id == sid
    assert not engine.ctx.subjects.cards("car")["c0"].suspended
    assert "notices" not in engine.messages[-3]
    told = str(fake.prompts[-1])
    assert "card_edits refused" in told
    assert "remove c0" in told
    assert "3 live cards" in told
    assert "card_edits refused" not in str(fake.prompts[-2])


def test_rewrite_of_the_live_card_waits_for_the_next_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The excerpt check would fetch the source: no network in tests.
    monkeypatch.setattr(card_rules, "source_problem", lambda *_a: None)
    _car(tmp_path)
    edit = CardEdit("edit", back="It is a better thing.")
    fake = FakeSession(turn(), turn("Fixed the answer.", card_edits=(edit,)))
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start(subject="car"))
    asyncio.run(engine.reply("the answer is wrong"))
    assert engine.ctx.subjects.cards("car")["c0"].back == "It is a better thing."
    assert engine.card is not None
    assert engine.card.back == "It is a thing."
    assert engine.messages[-1]["notices"] == ["Card updated: What is thing 0 of a?"]


def test_removing_the_last_open_card_stops_the_session(tmp_path: Path) -> None:
    _car(tmp_path, n=4)
    ctx, _ = make_ctx(tmp_path)
    for i in (1, 2, 3):
        taught(ctx, "car", f"c{i}", T0 - 1000, eid_n=i)
    fake = FakeSession(turn(), turn("Removed.", card_edits=(REMOVE,)))
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start(subject="car"))
    sid = engine.session_id
    asyncio.run(engine.reply("remove it"))
    assert engine.session_id == ""
    assert engine.ctx.subjects.cards("car")["c0"].suspended
    assert _events(tmp_path, sid)[-1]["type"] == "stop"


def test_the_unmigrated_deck_is_never_edited(tmp_path: Path) -> None:
    fake = FakeSession(turn(), turn("Removing.", card_edits=(REMOVE,)), turn())
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start())
    live = engine.card
    asyncio.run(engine.reply("remove it"))
    asyncio.run(engine.reply("and?"))
    assert engine.card == live
    assert "repo deck" in str(fake.prompts[-1])


def test_apply_edits_adds_to_the_live_cards_topic(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    found = {f"c{i}": card("a", i) for i in range(3)}
    found["d0"] = card("b", 0)
    mods = [module("a", status="ready", cards=3), module("b", status="ready")]
    subject(ctx, modules=mods, found=found)
    url = "https://example.org/coil"
    fakes.texts[url] = "A coil stores energy in its magnetic field when current flows."
    back = "Energy in its magnetic field while current flows."
    add = CardEdit("add", front="What does a coil store?", back=back, source=url)
    gone = CardEdit("remove", card="c0")
    done = edit_flow.apply_edits(ctx, "car", "d0", (add, gone))
    assert done.notices == ["Card added: What does a coil store?"]
    assert done.refusals == [
        (
            "remove c0: removing c0 would leave module a with 2 live cards; it needs "
            "at least 3 live cards"
        )
    ]
    assert done.removed_live == ""
    added = [c for c in ctx.subjects.cards("car").values() if c.source == url]
    assert [c.module for c in added] == ["b"]
