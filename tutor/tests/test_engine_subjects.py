# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The engine across subjects: refused switches, resume, card_done by subject."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import migrate
from tutor.curriculum.errors import RequestError
from tutor.curriculum.source import transcript_subject
from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fakes import FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

CLOCK_S = 1_800_000_000.0


def _engine(root: Path, fake: FakeSession) -> Engine:
    return Engine(
        store=Store(root), now=ManualClock(CLOCK_S), session_factory=lambda _p: fake
    )


def _car(root: Path) -> None:
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(12)}
    mods = [module("a", status="ready"), module("b", "a"), module("c", "b")]
    subject(ctx, modules=mods, found=found)


def test_a_refused_switch_leaves_the_live_session_alone(tmp_path: Path) -> None:
    migrate.migrate(tmp_path)
    _car(tmp_path)
    fake = FakeSession(turn(), turn("Done.", card_done=True))
    engine = _engine(tmp_path, fake)
    first = asyncio.run(engine.start())["card"]["id"]
    with pytest.raises(RequestError) as err:
        asyncio.run(engine.start("nope", subject="car"))
    assert err.value.code == "unknown_card"
    assert engine.source.subject == "automation"
    asyncio.run(engine.reply("my answer"))
    taught = [e for e in engine.ctx.log.read() if e["c"] == first]
    assert [(e["k"], e["s"]) for e in taught] == [("taught", "automation")]


def test_resume_picks_the_transcripts_subject(tmp_path: Path) -> None:
    _car(tmp_path)
    live = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(live.start(subject="car"))
    assert (
        transcript_subject(tmp_path / "sessions" / f"{live.session_id}.jsonl") == "car"
    )
    again = _engine(tmp_path, FakeSession())
    assert again.source.subject == "automation"
    assert again.resume_latest()
    assert (again.source.subject, again.card and again.card.id) == ("car", "c0")


def test_resume_of_a_vanished_subject_stays_put(tmp_path: Path) -> None:
    _car(tmp_path)
    live = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(live.start(subject="car"))
    shutil.rmtree(tmp_path / "subjects" / "car")
    again = _engine(tmp_path, FakeSession())
    assert not again.resume_latest()
    assert again.source.subject == "automation"


def test_card_done_for_another_subject(tmp_path: Path) -> None:
    migrate.migrate(tmp_path)
    _car(tmp_path)
    engine = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(engine.start())
    asyncio.run(engine.set_card_done("c0", done=True, subject="car"))
    assert engine.source.subject == "automation"
    event = engine.ctx.log.read()[-1]
    assert (event["k"], event["s"], event["c"], event["session"]) == (
        "taught",
        "car",
        "c0",
        "manual",
    )
    assert not engine.state()["card_done"]


def test_transcript_subject_edge_cases(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text(
        "\n" + json.dumps({"type": "learner"}) + "\n[1]\n", encoding="utf-8"
    )
    assert transcript_subject(path) is None
    path.write_text(json.dumps({"type": "start", "card": "x"}) + "\n", encoding="utf-8")
    assert transcript_subject(path) is None
