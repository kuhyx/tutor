# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the SQL lesson tests: model fake, calls, stored state."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tutor import outage
from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.relay import sql_lesson
from tutor.relay.errors import RequestError, classify
from tutor.store import data_dir
from tutor.tests._sql_support import call

REAL = {"ok": True, "error": None, "columns": ["name"], "rows": [["Ann"], ["Bo"]]}


def turn(**kw: Any) -> dict[str, Any]:
    base = {
        "verdict": "start",
        "feedback_md": "",
        "mastered": False,
        "summary_md": "",
        "question_md": "What does `SELECT name FROM c` return, and why?",
        "query": "SELECT name FROM c",
    }
    return base | kw


class FakeModel:
    def __init__(self, *answers: dict[str, Any] | Exception) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, system: str, text: str, schema: dict[str, Any]) -> Any:
        assert "Socratic" in system
        assert "verdict" in schema["properties"]
        self.prompts.append(text)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def model(monkeypatch: pytest.MonkeyPatch, *answers: Any) -> FakeModel:
    fake = FakeModel(*answers)
    monkeypatch.setattr(sql_lesson, "ask_model", fake)
    return fake


def lesson(topic: str = "basics", **body: Any) -> dict[str, Any]:
    return call("sql_lesson_turn", {"topic": topic, **body})


def state_of(lesson_id: str) -> dict[str, Any]:
    path = data_dir() / "sql_lessons" / f"{lesson_id}.json"
    return dict(json.loads(path.read_text(encoding="utf-8")))


def refused(**body: Any) -> RequestError:
    with pytest.raises(
        (RequestError, CurriculumError, outage.ClaudeUnavailableError)
    ) as caught:
        lesson(**body)
    return classify(caught.value)
