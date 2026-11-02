# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sql_lesson_turn``: the guided lesson state machine over fakes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor import outage
from tutor.relay.sql_lesson_plan import PLAN
from tutor.relay.sql_protocol import TOPICS
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


def test_every_topic_has_a_plan_and_a_dataset_per_concept() -> None:
    assert set(PLAN) == set(TOPICS)
    assert all(c.dataset and c.goal for cs in PLAN.values() for c in cs)
    assert PLAN["basics"][0].title == "NULL comparisons"


def test_a_new_lesson_asks_the_opening_question_with_the_tables_pinned(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, turn())
    got = lesson()
    assert len(got["lesson_id"]) == 12
    assert got["question_md"].startswith("What does")
    assert got["turn"] == 1
    assert got["progress"] == {
        "concept": "NULL comparisons",
        "index": 0,
        "total": 2,
        "phase": "teach",
        "checks_left": 0,
    }
    assert "c" in got["tables"]
    assert not {"feedback_md", "summary_md", "result", "done"} & set(got)
    assert "Opening question" in fake.prompts[0]
    assert ("get_drill", "t01_null_not_equal") in sd.calls
    assert ("run", ("t01_null_not_equal", "SELECT name FROM c")) in sd.calls
    assert fp.activity == []
    assert state_of(got["lesson_id"])["pending"]["rows"] == REAL["rows"]


def test_resuming_returns_the_same_turn_without_the_model(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    first = lesson()
    model(monkeypatch)
    again = lesson(lesson_id=first["lesson_id"])
    assert again.pop("thread") == [{"mine": False, "md": first["question_md"]}]
    assert again == first
    assert fp.activity == []


def test_a_wrong_reason_is_probed_not_confirmed_and_hides_the_result(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson()["lesson_id"]
    fake = model(
        monkeypatch,
        turn(
            verdict="wrong_reasoning",
            feedback_md="Right list. What about `NOT (referee = 2)`?",
            question_md="Now `WHERE NOT (referee = 2)`: which rows?",
            query="SELECT name FROM c WHERE NOT (referee = 2)",
        ),
    )
    got = lesson(lesson_id=lid, answer="Ann, Bo because NULL != 2")
    assert "NOT (referee" in got["feedback_md"]
    assert "result" not in got
    assert got["progress"]["phase"] == "teach"
    assert got["turn"] == 2
    text = fake.prompts[0]
    assert '[["Ann"], ["Bo"]]' in text
    assert "NULL != 2" in text
    assert [a["source"] for a in fp.activity] == ["sql_drills"]
    saved = state_of(lid)
    assert saved["history"][-1]["verdict"] == "wrong_reasoning"
    assert saved["pending"]["query"].startswith("SELECT name FROM c WHERE NOT")


def test_a_correct_answer_shows_the_real_result_but_is_not_yet_mastery(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson()["lesson_id"]
    model(monkeypatch, turn(verdict="correct", feedback_md="Yes."))
    got = lesson(lesson_id=lid, answer="Ann and Bo, no NULLs involved")
    assert got["result"] == {"columns": ["name"], "rows": REAL["rows"]}
    assert got["progress"]["phase"] == "teach"
    assert "summary_md" not in got


def master(
    lid: str, monkeypatch: pytest.MonkeyPatch, topic: str = "basics"
) -> dict[str, Any]:
    model(
        monkeypatch,
        turn(
            verdict="correct",
            mastered=True,
            summary_md="| a | b | UNKNOWN |",
            question_md="Mini-check 1: `SELECT name FROM c`?",
        ),
    )
    return lesson(topic, lesson_id=lid, answer="NULL is unknown, not false")


def test_stating_the_rule_gives_the_summary_and_starts_the_mini_checks(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson()["lesson_id"]
    got = master(lid, monkeypatch)
    assert got["summary_md"] == "| a | b | UNKNOWN |"
    assert got["progress"]["phase"] == "check"
    assert got["progress"]["checks_left"] == 2


def test_two_right_mini_checks_advance_to_the_next_concept(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson()["lesson_id"]
    master(lid, monkeypatch)
    model(monkeypatch, turn(verdict="correct", question_md="Check 2?"))
    got = lesson(lesson_id=lid, answer="a")
    assert (got["progress"]["phase"], got["progress"]["checks_left"]) == ("check", 1)
    assert got["question_md"] == "Check 2?"
    fake = model(
        monkeypatch,
        turn(verdict="correct", feedback_md="Concept done."),
        turn(question_md="ON vs WHERE: which rows?"),
    )
    got = lesson(lesson_id=lid, answer="b")
    assert got["progress"]["index"] == 1
    assert got["progress"]["concept"] == "JOIN ON vs WHERE"
    assert (got["progress"]["phase"], got["progress"]["checks_left"]) == ("teach", 0)
    assert got["question_md"] == "ON vs WHERE: which rows?"
    assert got["feedback_md"] == "Concept done."
    assert ("get_drill", "t03_left_join_on") in sd.calls
    assert "JOIN ON vs WHERE" in fake.prompts[1]
    assert "Opening question" in fake.prompts[1]


def test_a_wrong_mini_check_goes_back_to_teaching(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson()["lesson_id"]
    master(lid, monkeypatch)
    model(monkeypatch, turn(verdict="wrong_prediction", feedback_md="Look again."))
    got = lesson(lesson_id=lid, answer="z")
    assert (got["progress"]["phase"], got["progress"]["checks_left"]) == ("teach", 0)
    assert "result" not in got


def test_the_last_concept_ends_the_lesson(
    sd: FakeSd, fp: FakeFp, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    lid = lesson("joins-null")["lesson_id"]
    master(lid, monkeypatch, "joins-null")
    model(monkeypatch, turn(verdict="correct"))
    lesson("joins-null", lesson_id=lid, answer="a")
    model(monkeypatch, turn(verdict="correct", feedback_md="All done."))
    got = lesson("joins-null", lesson_id=lid, answer="b")
    assert got["done"] is True
    assert "question_md" not in got
    assert got["feedback_md"] == "All done."
    assert lesson("joins-null", lesson_id=lid)["done"] is True
    err = refused(topic="joins-null", lesson_id=lid, answer="more")
    assert (err.code, "finished" in err.message) == ("bad_request", True)


def test_bad_references_are_bad_requests(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, turn())
    assert refused(answer="hello").code == "bad_request"
    assert refused(lesson_id="0" * 12).code == "bad_request"
    lid = lesson()["lesson_id"]
    other = refused(topic="pivot", lesson_id=lid)
    assert other.code == "bad_request"
    assert "pivot" in other.message
    corrupt = data_dir() / "sql_lessons" / f"{'1' * 12}.json"
    corrupt.write_text("[1]", encoding="utf-8")
    assert refused(lesson_id="1" * 12).code == "bad_request"


def test_an_outage_refuses_before_any_model_call(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    down = outage.ClaudeUnavailableError("rate_limit", 99)

    def boom(now: float) -> None:
        raise down

    monkeypatch.setattr(outage, "ensure_available", boom)
    assert refused().code == "claude_unavailable"
