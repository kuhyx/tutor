# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sql_lesson_turn``: the stored conversation returned on resume."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.relay import sql_lesson
from tutor.tests._sql_lesson_support import REAL, lesson, model, turn
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


def test_resume_returns_the_whole_conversation_in_order(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn(question_md="First?"))
    lid = lesson()["lesson_id"]
    model(
        monkeypatch,
        turn(verdict="wrong_reasoning", feedback_md="Probe.", question_md="Second?"),
    )
    lesson(lesson_id=lid, answer="Ann, Bo because x")
    model(
        monkeypatch,
        turn(
            verdict="correct",
            mastered=True,
            feedback_md="Yes.",
            summary_md="| sum |",
            question_md="Third?",
        ),
    )
    lesson(lesson_id=lid, answer="rule")
    model(monkeypatch)
    grid = {"columns": ["name"], "rows": REAL["rows"]}
    assert lesson(lesson_id=lid)["thread"] == [
        {"mine": False, "md": "First?"},
        {"mine": True, "md": "Ann, Bo because x"},
        {"mine": False, "md": "Probe."},
        {"mine": False, "md": "Second?"},
        {"mine": True, "md": "rule"},
        {"mine": False, "md": "Yes."},
        {"mine": False, "grid": grid},
        {"mine": False, "md": "| sum |"},
        {"mine": False, "md": "Third?"},
    ]


def test_the_stored_thread_is_capped_keeping_the_newest(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn(question_md="Zero?"))
    lid = lesson()["lesson_id"]
    for i in range(1, 80):
        model(monkeypatch, turn(verdict="wrong_prediction", question_md=f"Next {i}?"))
        lesson(lesson_id=lid, answer=f"a{i}")
    thread = lesson(lesson_id=lid)["thread"]
    assert len(thread) == sql_lesson.KEEP_THREAD
    assert thread[-1] == {"mine": False, "md": "Next 79?"}
