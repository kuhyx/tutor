# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A lesson's first probe after a wrong answer never names a function or clause."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay import sql_lesson_checks as probe
from tutor.tests._sql_lesson_support import (
    REAL,
    lesson,
    model,
    state_of,
    turn,
)
from tutor.tests._sql_support import FakeSd, install_fake_fp, install_fake_sd

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp

NAMING = turn(
    verdict="wrong_prediction",
    feedback_md="Not quite. Have you thought about ROUND on that column?",
)
CLEAN = turn(
    verdict="wrong_prediction",
    feedback_md="Not quite. Look at the table: which rows have an empty cell?",
)


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    fake = install_fake_sd(monkeypatch)
    fake.run_result = dict(REAL)
    return fake


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    return install_fake_fp(monkeypatch)


def _opened(monkeypatch: pytest.MonkeyPatch) -> str:
    model(monkeypatch, turn())
    return str(lesson()["lesson_id"])


def test_a_named_function_in_the_first_probe_is_re_asked(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = _opened(monkeypatch)
    fake = model(monkeypatch, NAMING, CLEAN)
    got = lesson(lesson_id=lid, answer="Ann only")
    assert "empty cell" in got["feedback_md"]
    assert len(fake.prompts) == 2
    assert "round" in fake.prompts[1]
    assert "only points at the rule" in fake.prompts[1]


def test_a_name_the_learner_typed_is_allowed(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = _opened(monkeypatch)
    fake = model(monkeypatch, NAMING)
    got = lesson(lesson_id=lid, answer="I would use round(x) here")
    assert "ROUND" in got["feedback_md"]
    assert len(fake.prompts) == 1


def test_three_naming_replies_fall_back_to_a_generic_nudge(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = _opened(monkeypatch)
    naming_question = turn(
        verdict="partial",
        feedback_md="Try COALESCE.",
        question_md="Which rows does the CASE query return?",
    )
    fake = model(monkeypatch, naming_question, naming_question, naming_question)
    got = lesson(lesson_id=lid, answer="Ann")
    assert len(fake.prompts) == 3
    assert got["feedback_md"] == probe.NUDGE
    assert got["question_md"] == (
        "```sql\nSELECT name FROM c\n```\n" + probe.GENERIC_QUESTION
    )
    assert state_of(lid)["pending"]["question_md"] == got["question_md"]
    assert got["turn"] == 2


def test_the_fallback_keeps_a_clean_question(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = _opened(monkeypatch)
    bad = turn(verdict="partial", feedback_md="Try COALESCE.")
    model(monkeypatch, bad, bad, bad)
    got = lesson(lesson_id=lid, answer="Ann")
    assert got["feedback_md"] == probe.NUDGE
    assert got["question_md"] == turn()["question_md"]


def test_only_the_first_probe_is_checked(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = _opened(monkeypatch)
    model(monkeypatch, CLEAN)
    lesson(lesson_id=lid, answer="Ann")
    fake = model(monkeypatch, NAMING)
    got = lesson(lesson_id=lid, answer="Bo")
    assert "ROUND" in got["feedback_md"]
    assert len(fake.prompts) == 1


def test_a_probe_after_a_correct_answer_is_a_first_probe_again(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    lid = _opened(monkeypatch)
    model(monkeypatch, turn(verdict="correct", feedback_md="Yes."))
    lesson(lesson_id=lid, answer="Ann and Bo")
    fake = model(monkeypatch, NAMING, CLEAN)
    lesson(lesson_id=lid, answer="Bo")
    assert len(fake.prompts) == 2


def test_a_correct_verdict_and_the_opening_are_not_checked(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn(question_md="Which rows does COUNT(*) give?"))
    lid = str(lesson()["lesson_id"])
    fake = model(monkeypatch, turn(verdict="correct", feedback_md="Use ROUND, yes."))
    got = lesson(lesson_id=lid, answer="Ann and Bo")
    assert "ROUND" in got["feedback_md"]
    assert len(fake.prompts) == 1


def _case(feedback: str, question: str, *, answer: str = "x") -> str | None:
    state: dict[str, Any] = {"history": []}
    got = turn(verdict="partial", feedback_md=feedback, question_md=question)
    return probe.problem(got, state, answer)


def test_sql_in_a_fence_is_not_prose() -> None:
    fenced = "Now this:\n```sql\nSELECT ROUND(x) FROM t\n```\nWhich rows?"
    assert _case("Look at the rule.", fenced) is None


@pytest.mark.parametrize(
    "word", ["HAVING", "CAST", "DATE_FORMAT", "CASE", "GROUP BY", "coalesce(x, 0)"]
)
def test_constructs_are_named(word: str) -> None:
    why = _case(f"Think about {word} here.", "Which rows?")
    assert why is not None
    assert "first probe" in why


def test_a_multi_word_name_needs_every_word_typed() -> None:
    assert _case("Think about GROUP BY.", "Which rows?", answer="group") is not None
    assert _case("Think about GROUP BY.", "Which rows?", answer="group by x") is None


def test_history_answers_count_as_typed() -> None:
    state: dict[str, Any] = {
        "history": [{"answer": "having", "verdict": "correct", "query": "q"}]
    }
    got = turn(verdict="partial", feedback_md="Check HAVING again.")
    assert probe.problem(got, state, "x") is None
