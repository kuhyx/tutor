# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The engine on a curriculum subject: pick, taught events, cap, profile."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import migrate
from tutor.curriculum.errors import RequestError
from tutor.curriculum.ids import ulid
from tutor.curriculum.records import Meta
from tutor.curriculum.source import DeckSource, SubjectSource, source_for
from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fakes import FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

DIAGRAM = {"title": "t", "circuits": []}


def _engine(root: Path, fake: FakeSession, clock: ManualClock | None = None) -> Engine:
    return Engine(
        store=Store(root), now=clock or ManualClock(), session_factory=lambda _p: fake
    )


def test_unmigrated_data_uses_the_deck(tmp_path: Path) -> None:
    engine = _engine(tmp_path, FakeSession())
    assert isinstance(engine.source, DeckSource)
    ctx, _ = make_ctx(tmp_path)
    with pytest.raises(RequestError, match="unknown subject"):
        source_for(engine.store, ctx, "car")


def test_migrated_automation_teaches_the_same_first_card(tmp_path: Path) -> None:
    legacy = _engine(tmp_path / "old", FakeSession(turn()))
    migrate.migrate(tmp_path / "new")
    fake = FakeSession(
        turn(),
        turn("Done.", card_done=True, concepts_mastered=["Relay"], diagram=DIAGRAM),
    )
    engine = _engine(tmp_path / "new", fake)
    assert isinstance(engine.source, SubjectSource)
    assert [c.id for c in engine.deck] == [c.id for c in legacy.deck]
    first = asyncio.run(engine.start())["card"]["id"]
    assert first == asyncio.run(legacy.start())["card"]["id"]
    state = asyncio.run(engine.reply("it is a computer"))
    assert state["card_done"]
    assert state["mastered"] == ["relay"]
    assert engine.source.done() == {first: {"session": engine.session_id}}
    assert engine.store.progress()["cards_done"][first]["session"] == engine.session_id
    log = engine.ctx.log.read()
    assert [(e["k"], e["c"]) for e in log] == [("taught", first)]
    asyncio.run(engine.set_card_done(first, done=False))
    assert engine.source.done() == {}
    assert engine.ctx.log.read()[-1]["k"] == "untaught"


def test_daily_cap_and_subject_switch_without_diagrams(tmp_path: Path) -> None:
    clock = ManualClock(1_800_000_000.0)
    ctx, _ = make_ctx(tmp_path)
    many = {f"c{i}": card("a", i) for i in range(27)}
    subject(
        ctx,
        modules=[module("a", status="ready"), module("b", "a"), module("c", "b")],
        found=many,
    )
    now = int(clock() * 1000)
    ctx.log.append(
        [
            {
                "dev": "d",
                "eid": ulid(now - i, bytes([i] * 10)),
                "k": "taught",
                "s": "car",
                "c": f"c{i}",
                "at": now - i,
            }
            for i in range(25)
        ]
    )
    fake = FakeSession(turn("hi", diagram=DIAGRAM), turn("x"))
    engine = _engine(tmp_path, fake, clock)
    with pytest.raises(RequestError) as err:
        asyncio.run(engine.start(subject="car"))
    assert err.value.code == "daily_new_cap"
    state = asyncio.run(engine.start("c1", subject="car"))  # re-teaching is free
    assert state["card"]["id"] == "c1"
    assert state["messages"][0]["diagrams"] == []  # car has no diagrams
    assert engine.source.profile.diagrams is False
    assert "industrial automation" not in fake_prompt(engine)
    clock.advance(2 * 86400)
    assert asyncio.run(engine.next_card())["card"]["id"] == "c25"


def fake_prompt(engine: Engine) -> str:
    return engine._prompt(engine.deck[0])


def test_subject_without_a_plan_or_profile(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    ctx.subjects.commit("car", Meta("Cars", "g", "drafting", 1))
    src = SubjectSource(Store(tmp_path), ctx, "car")
    assert src.profile.subject == "car"
    with pytest.raises(RequestError, match="no plan yet"):
        src.cards()


def test_subject_concepts(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, found={"a1": card("a", 1)})
    src = SubjectSource(Store(tmp_path), ctx, "car")
    assert src.master(["piston", "piston", "valve"], "a1", "s1") == ["piston", "valve"]
    assert src.master(["piston"], "a1", "s1") == []
    assert src.mastered() == ["piston", "valve"]


def test_no_card_left_reads_the_title_and_ignores_the_skip(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, found={"a1": card("a", 1), "a2": card("a", 2)})
    ctx.log.append(
        [
            {
                "dev": "d",
                "eid": ulid(1_800_000_000_000, bytes(10)),
                "k": "taught",
                "s": "car",
                "c": "a1",
                "at": 1_800_000_000_000,
            }
        ]
    )
    src = SubjectSource(Store(tmp_path), ctx, "car")
    with pytest.raises(RequestError) as err:
        src.pick(None, skip="a2")  # a2 is untaught: "a" is not fully taught
    assert err.value.code == "no_card_left"
    assert err.value.extra["subject_title"] == "Cars"
    assert err.value.extra["next"] == "reviews_due"


def test_deck_source_skip_and_none_left(tmp_path: Path) -> None:
    src = DeckSource(Store(tmp_path))
    first = src.pick(None)
    assert src.pick(None, skip=first.id).id != first.id
    for c in src.cards():
        src.store.finish_card(c.id, "s")
    with pytest.raises(RequestError, match="no unfinished card left"):
        src.pick(None, skip=first.id)
    assert src.master(["x"], "c", "s") == ["x"]
    assert src.mastered() == ["x"]
