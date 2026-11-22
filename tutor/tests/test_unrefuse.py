# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The one-off repair of a ``card_done`` the old gate refused (faa43ba fixed the gate).

Live 2026-11-22: ``histogram-prefix-sorted-position`` was called passed by the
tutor but logged ``card_done_refused: [direct-index-counting-array]``, a
prerequisite of a module C3 refuses, which the shared rule now waives. Nothing
re-applied the word, so the card, the module state and the page stayed open.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tutor import repair
from tutor.tests._phase import LC, grant
from tutor.tests._unrefuse import (
    SID,
    engine_for,
    flips,
    refused_session,
    src,
    taught,
    transcript,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_refusal_the_gate_no_longer_makes_is_applied(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    grant((LC, "b"))  # THEORY(b); a is refused, so a0 holds nothing shut
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    assert taught(engine) == {"b0"}
    with caplog.at_level(logging.INFO):
        assert engine.unrefuse_done_cards() == [("b1", SID)]
    assert taught(engine) == {"b0", "b1"}
    assert engine.store.progress()["cards_done"]["b1"]["session"] == SID
    assert flips(tmp_path) == [("b", True)]  # the normal writer's row
    assert f"marked b1 done from session {SID}" in caplog.text
    assert engine.resume_path(tmp_path / "sessions" / f"{SID}.jsonl")
    state = engine.state()
    assert state["card"]["id"] == "b1"
    assert state["card_done"] is True


def test_the_page_after_the_repair_offers_the_next_card(tmp_path: Path) -> None:
    grant((LC, "a"), (LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("a0", "earlier", done=True)  # a0 done: b1 was never blocked
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    assert engine.unrefuse_done_cards() == [("b1", SID)]
    assert engine.resume_path(tmp_path / "sessions" / f"{SID}.jsonl")
    assert engine.state()["card_done"] is True


def test_a_refusal_still_blocked_by_a_prerequisite_stays_refused(
    tmp_path: Path,
) -> None:
    grant((LC, "a"), (LC, "b"))  # a is teachable: a0 really is missing
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    before = transcript(tmp_path)
    assert engine.unrefuse_done_cards() == []
    assert taught(engine) == {"b0"}
    assert transcript(tmp_path) == before


def test_a_refusal_in_a_module_c3_refuses_now_stays_refused(tmp_path: Path) -> None:
    grant((LC, "a"))  # b is refused now
    engine = engine_for(tmp_path)
    src(engine).mark("a0", "earlier", done=True)
    refused_session(engine)
    assert engine.unrefuse_done_cards() == []
    assert "b1" not in taught(engine)


def test_running_it_twice_changes_nothing(tmp_path: Path) -> None:
    grant((LC, "b"))
    engine = engine_for(tmp_path)
    src(engine).mark("b0", "earlier", done=True)
    refused_session(engine)
    assert engine.unrefuse_done_cards() == [("b1", SID)]
    snapshot = (
        transcript(tmp_path),
        (tmp_path / "progress.json").read_text().split('"repairs"')[0],
        flips(tmp_path),
    )
    assert engine.unrefuse_done_cards() == []
    assert engine.store.repaired(repair.UNREFUSE) is True
    assert (
        transcript(tmp_path),
        (tmp_path / "progress.json").read_text().split('"repairs"')[0],
        flips(tmp_path),
    ) == snapshot
