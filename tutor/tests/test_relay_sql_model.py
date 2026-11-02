# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sql_hint`` and ``sql_generate``: the model calls and what they may return."""

from __future__ import annotations

from typing import Any

import pytest

from tutor import outage
from tutor.curriculum.errors import MODEL_ERROR
from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.relay import sql_model
from tutor.relay.errors import RequestError, classify
from tutor.tests._sql_support import (
    EngineError,
    FakeSd,
    call,
    install_fake_fp,
    install_fake_sd,
)

GOOD = "Which rows survive the WHERE clause when a column is NULL?"
SPEC = {
    "title": "Orders per customer",
    "topic": "window",
    "task_md": "Show each customer and their order count.",
    "schema_sql": "CREATE TABLE o (id INT);",
    "reference_sql": "SELECT 1",
}


class FakeModel:
    """Queued answers (dicts, or exceptions to raise); records every prompt."""

    def __init__(self, *answers: dict[str, Any] | Exception) -> None:
        self.answers = list(answers)
        self.prompts: list[tuple[str, str]] = []
        self.schemas: list[dict[str, Any]] = []

    def __call__(self, system: str, prompt: str, schema: dict[str, Any]) -> Any:
        self.prompts.append((system, prompt))
        self.schemas.append(schema)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def model(
    monkeypatch: pytest.MonkeyPatch, *answers: dict[str, Any] | Exception
) -> FakeModel:
    fake = FakeModel(*answers)
    monkeypatch.setattr(sql_model, "ask_model", fake)
    return fake


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    install_fake_fp(monkeypatch)
    return install_fake_sd(monkeypatch)


def refused(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(
        (RequestError, CurriculumError, outage.ClaudeUnavailableError)
    ) as caught:
        call(kind, body)
    return classify(caught.value)


def test_a_hint_is_one_question_built_from_the_task_not_the_answer(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, {"question": f"  {GOOD}  "})
    got = call(
        "sql_hint",
        {
            "id": "q1",
            "sql": "SELECT * FROM c WHERE x = NULL",
            "last_result": {"ok": True, "match": False, "rows": [["0"]]},
            "history": ["What does NULL mean?"],
        },
    )
    assert got == {"question": GOOD}
    system, prompt = fake.prompts[0]
    assert "ONE" in system
    assert "never" in system.lower()
    for needle in (
        "List every customer.",
        "CREATE TABLE c",
        "x = NULL",
        "What does NULL mean?",
        '"match": false',
    ):
        assert needle in prompt
    assert fake.schemas[0]["required"] == ["question"]


def test_a_hint_without_work_yet_says_so(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, {"question": GOOD})
    call("sql_hint", {"id": "q1"})
    assert "has not written any SQL yet" in fake.prompts[0][1]


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "Try this: ```sql\nSELECT 1\n```?",
        "Have you tried SELECT name FROM customers WHERE id = 1?",
        "Why not DELETE FROM customers? Or truncate?",
        "Think about NULL.",
        "Why? Because? " + "x" * 10,
        "Why " + "x" * 400 + "?",
    ],
)
def test_a_hint_that_hands_over_code_or_is_no_single_question_is_re_asked(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    fake = model(monkeypatch, {"question": bad}, {"question": GOOD})
    assert call("sql_hint", {"id": "q1"}) == {"question": GOOD}
    assert "rejected" in fake.prompts[1][1]


def test_a_hint_gives_up_after_two_retries_as_a_retryable_model_error(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, *[{"question": "SELECT a FROM b"}] * 3)
    err = refused("sql_hint", {"id": "q1"})
    assert (err.code, err.retry) == ("model_error", True)
    assert len(fake.prompts) == 3


def test_a_hint_for_an_unknown_drill_never_reaches_the_model(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch)
    assert refused("sql_hint", {"id": "nope"}).code == "bad_request"
    assert fake.prompts == []


def test_model_failures_keep_their_codes(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    model(monkeypatch, CurriculumError(MODEL_ERROR, "the model call failed: x"))
    assert refused("sql_hint", {"id": "q1"}).code == "model_error"
    down = outage.ClaudeUnavailableError("rate_limit", 99)
    model(monkeypatch, CurriculumError("claude_unavailable", "down"))
    assert refused("sql_generate", {"topic": "window"}).code == "claude_unavailable"
    monkeypatch.setattr(
        outage, "ensure_available", lambda now: (_ for _ in ()).throw(down)
    )
    for kind, body in (
        ("sql_hint", {"id": "q1"}),
        ("sql_generate", {"topic": "pivot"}),
    ):
        err = refused(kind, body)
        assert (err.code, err.extra["resets_at"]) == ("claude_unavailable", 99)


def test_generate_saves_the_spec_with_the_requested_topic(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, {**SPEC, "topic": "strings"})
    got = call("sql_generate", {"topic": "basics", "difficulty": "hard"})
    assert got["id"] == "g2"  # the fake sd's get_drill echoes the id it is asked
    assert sd.saved == [{**SPEC, "topic": "basics"}]
    assert ("ensure_running", None) in sd.calls
    system, prompt = fake.prompts[0]
    assert "MySQL 8.0.33" in system
    assert "company" in system.lower()
    assert "basics" in prompt
    assert "hard" in prompt
    assert "Null trap" in prompt  # the topic's existing titles, to vary
    assert set(fake.schemas[0]["required"]) == set(SPEC)


def test_generate_retries_a_rejected_spec_with_the_reason_then_succeeds(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    sd.save_errors = [ValueError("reference SQL returns no rows")]
    fake = model(monkeypatch, SPEC, SPEC)
    call("sql_generate", {"topic": "window"})
    assert "reference SQL returns no rows" in fake.prompts[1][1]
    assert len(sd.saved) == 1


def test_generate_gives_up_after_two_retries(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    sd.save_errors = [ValueError("empty"), ValueError("errors"), ValueError("empty")]
    fake = model(monkeypatch, SPEC, SPEC, SPEC, SPEC)
    err = refused("sql_generate", {"topic": "window"})
    assert (err.code, err.retry) == ("model_error", True)
    assert "empty" in err.message
    assert len(fake.prompts) == 3


def test_generate_re_asks_when_a_spec_field_is_blank_or_missing(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = model(monkeypatch, {**SPEC, "reference_sql": "  "}, {"title": "x"}, SPEC)
    call("sql_generate", {"topic": "window"})
    assert "reference_sql" in fake.prompts[1][1]
    assert "task_md" in fake.prompts[2][1]
    assert sd.calls.count(("save_generated", {**SPEC, "topic": "window"})) == 1


def test_an_engine_failure_while_generating_is_not_retried(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    sd.save_errors = [EngineError("docker gone")]
    fake = model(monkeypatch, SPEC, SPEC)
    err = refused("sql_generate", {"topic": "window"})
    assert (err.code, err.retry) == ("worker_error", True)
    assert len(fake.prompts) == 1


def test_a_predict_drill_hint_shows_the_query_to_predict(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = sd.get_drill
    monkeypatch.setattr(
        sd, "get_drill", lambda i: {**original(i), "query": "SELECT NULL = NULL"}
    )
    fake = model(monkeypatch, {"question": GOOD})
    call("sql_hint", {"id": "q1"})
    assert "predict the output of:\nSELECT NULL = NULL" in fake.prompts[0][1]
