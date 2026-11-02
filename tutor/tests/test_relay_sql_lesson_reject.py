# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sql_lesson_turn``: turns the model gets wrong are re-asked, never stored."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.store import data_dir
from tutor.tests._sql_lesson_support import (
    REAL,
    lesson,
    model,
    refused,
    state_of,
    turn,
)
from tutor.tests._sql_support import FakeSd, install_fake_fp, install_fake_sd

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    fake = install_fake_sd(monkeypatch)
    fake.run_result = dict(REAL)
    return fake


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    return install_fake_fp(monkeypatch)


@pytest.mark.parametrize(
    ("bad", "needle"),
    [
        (turn(verdict="great"), "verdict"),
        (turn(question_md="  "), "question_md is empty"),
        (turn(query=""), "query is empty"),
        (turn(feedback_md=5), "must be strings"),
        (
            turn(query="SELECT 1", question_md="x", verdict="correct", mastered=True),
            "summary_md",
        ),
    ],
)
def test_an_invalid_turn_is_re_asked_with_the_reason(
    sd: FakeSd,
    fp: FakeFp,
    monkeypatch: pytest.MonkeyPatch,
    bad: dict[str, Any],
    needle: str,
) -> None:
    fake = model(monkeypatch, turn(), bad, turn(verdict="wrong_prediction"))
    lid = lesson()["lesson_id"]
    lesson(lesson_id=lid, answer="x")
    assert needle in fake.prompts[2]


def test_a_failing_or_empty_query_is_re_asked(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, turn(), turn(), turn())
    sd.run_result = {"ok": False, "error": "ERROR 1054 unknown column", "rows": []}
    original = sd.run

    def flaky(drill_id: str, text: str) -> dict[str, Any]:
        out = original(drill_id, text)
        sd.run_result = {**REAL, "rows": []} if len(fake.prompts) == 1 else dict(REAL)
        return out

    monkeypatch.setattr(sd, "run", flaky)
    lesson()
    assert "unknown column" in fake.prompts[1]
    assert "no rows" in fake.prompts[2]


def test_a_turn_that_spells_out_the_result_is_rejected(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    sd.run_result = {**REAL, "columns": ["a", "b"], "rows": [["Ann", "7"], ["Bo", "9"]]}
    leak = turn(question_md="It returns Ann | 7, right?")
    fake = model(monkeypatch, leak, turn(), turn())
    lid = lesson()["lesson_id"]
    assert "spells out" in fake.prompts[1]
    fake = model(
        monkeypatch,
        turn(verdict="wrong_prediction", feedback_md="It was Ann, 7"),
        turn(),
    )
    lesson(lesson_id=lid, answer="x")
    assert "reveals" in fake.prompts[1]


def test_giving_up_keeps_the_stored_state_and_is_retryable(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson()["lesson_id"]
    before = state_of(lid)
    model(monkeypatch, *[turn(verdict="nope")] * 3)
    err = refused(lesson_id=lid, answer="x")
    assert (err.code, err.retry) == ("model_error", True)
    assert state_of(lid) == before
    assert fp.activity == []


def test_a_new_lesson_never_started_leaves_no_file_when_the_model_fails(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, *[turn(query="")] * 3)
    assert refused().code == "model_error"
    assert not (data_dir() / "sql_lessons").exists()


def test_a_turn_that_points_at_an_earlier_query_must_restate_it(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The learner never scrolls: "rewrite Q1" carries Q1's SQL inline."""
    bare = turn(
        verdict="wrong_prediction",
        question_md="Rewrite the earlier query so it keeps Ann.\n```sql\nSELECT 2\n```",
        query="SELECT 2",
    )
    inline = turn(
        verdict="wrong_prediction",
        question_md=(
            "Rewrite this earlier query so it keeps Ann:\n"
            "```sql\nSELECT   name FROM c\n```"
        ),
        query="SELECT 2",
    )
    fake = model(monkeypatch, turn(), bare, inline)
    lid = lesson()["lesson_id"]
    got = lesson(lesson_id=lid, answer="x")
    assert "restate" in fake.prompts[2]
    assert "SELECT   name FROM c" in got["question_md"]
    assert "restate" not in fake.prompts[1]


def test_the_system_prompt_forbids_scrolling_back() -> None:
    from tutor.relay import sql_lesson_prompt as prompt

    assert "never scroll" in prompt.SYSTEM
    assert prompt.missing_backref("Rewrite Q6 now", ["SELECT 1"]) is not None
    assert prompt.missing_backref("What is NULL = NULL?", ["SELECT 1"]) is None
    assert prompt.missing_backref("Rewrite Q6 now", []) is None
