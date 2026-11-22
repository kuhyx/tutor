# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The unrefuse repair leaves what was decided since, and what it cannot read."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tutor import repair
from tutor.curriculum.source import SubjectSource
from tutor.tests._phase import LC, grant
from tutor.tests._unrefuse import (
    LATER,
    REFUSED,
    SID,
    engine_for,
    log,
    refused_session,
    src,
    taught,
    transcript,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_card_done_since_keeps_its_own_session(tmp_path: Path) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    src(engine).mark("b1", "later-session", done=True)  # accepted afterwards
    before = transcript(tmp_path)
    assert engine.unrefuse_done_cards() == []
    assert engine.store.progress()["cards_done"]["b1"]["session"] == "later-session"
    assert transcript(tmp_path) == before


def test_a_manual_undo_after_the_refusal_is_not_redone(tmp_path: Path) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    log(
        engine,
        SID,
        {"type": "card_done_manual", "card": "b1", "done": False, "logged_at": LATER},
    )
    assert engine.unrefuse_done_cards() == []
    assert "b1" not in taught(engine)


def test_a_manual_undo_in_another_session_is_not_redone(tmp_path: Path) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    log(
        engine,
        "20261123-090000-aaaa",
        {"type": "start", "card": "b0", "subject": LC},
        {"type": "card_done_manual", "card": "b1", "done": False, "logged_at": LATER},
    )
    assert engine.unrefuse_done_cards() == []
    assert "b1" not in taught(engine)


def test_an_old_manual_done_before_the_refusal_does_not_hide_it(
    tmp_path: Path,
) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    log(
        engine,
        "20261120-090000-aaaa",
        {"type": "start", "card": "b1", "subject": LC},
        {
            "type": "card_done_manual",
            "card": "b1",
            "done": False,
            "logged_at": "2026-11-20T09:00:00+00:00",
        },
    )
    refused_session(engine)
    assert engine.unrefuse_done_cards() == [("b1", SID)]


def test_unreadable_lines_and_unknown_things_are_skipped_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    with (tmp_path / "sessions" / f"{SID}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"type": "tut\n[1, 2]\n')
    log(  # a card the deck no longer has, a subject nobody knows, no start at all
        engine,
        "gone-card",
        {"type": "start", "card": "zz", "subject": LC},
        {"type": "tutor", "turn": dict(REFUSED)},
    )
    log(
        engine,
        "gone-subject",
        {"type": "start", "card": "b1", "subject": "no-such-subject"},
        {"type": "tutor", "turn": dict(REFUSED)},
    )
    log(engine, "no-start", {"type": "tutor", "turn": dict(REFUSED)})
    with caplog.at_level(logging.WARNING):
        assert engine.unrefuse_done_cards() == [("b1", SID)]
    assert "unreadable line" in caplog.text
    assert "zz" in caplog.text
    assert "no-such-subject" in caplog.text


def test_a_mark_the_source_refuses_is_logged_not_raised(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)

    def refuse(*_a: Any, **_k: Any) -> None:
        msg = "nope"
        raise ValueError(msg)

    monkeypatch.setattr(SubjectSource, "mark", refuse)
    with caplog.at_level(logging.WARNING):
        assert engine.unrefuse_done_cards() == []
    assert "nope" in caplog.text
    assert engine.store.repaired(repair.UNREFUSE) is True


def test_a_data_dir_without_sessions_is_nothing_to_repair(tmp_path: Path) -> None:
    engine = engine_for(tmp_path)
    assert engine.unrefuse_done_cards() == []
    assert engine.store.repaired(repair.UNREFUSE) is True


def test_the_startup_runs_it_before_the_resume(tmp_path: Path) -> None:
    from tutor.relay import cli

    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    asyncio.run(engine.close())
    cli.prepare(engine, fresh=True)
    assert taught(engine) == {"b0", "b1"}
