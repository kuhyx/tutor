# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request validation of the ``sql_*`` kinds."""

from __future__ import annotations

from typing import Any

import pytest

from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import RequestError
from tutor.tests._sql_support import validate


def bad(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        validate(kind, body)
    assert caught.value.code == "bad_request"
    return caught.value


def test_the_kinds_are_chat_lane_kinds_with_handlers() -> None:
    for kind in (
        "sql_list",
        "sql_get",
        "sql_run",
        "sql_predict",
        "sql_hint",
        "sql_generate",
        "sql_lesson_turn",
    ):
        assert protocol.KINDS[kind][0] == protocol.CHAT
        assert kind in CHAT_HANDLERS
    assert validate("sql_list", {"x": 1}).body == {}


def test_ids_and_sql_are_checked() -> None:
    assert validate("sql_get", {"id": "q1.a_b-C"}).body == {"id": "q1.a_b-C"}
    for drill_id in ("", "a b", "x" * 65, "../x", 5, None):
        bad("sql_get", {"id": drill_id})
    assert validate("sql_run", {"id": "q1", "sql": "SELECT 1"}).body["sql"]
    for text in ("", "  \n", "x" * 8001, 7, None):
        bad("sql_run", {"id": "q1", "sql": text})


def test_a_grid_is_rows_of_string_cells_and_may_be_absent() -> None:
    assert validate("sql_predict", {"id": "q1"}).body["grid"] == []
    grid = [["1", ""], ["NULL", "x"]]
    assert validate("sql_predict", {"id": "q1", "grid": grid}).body["grid"] == grid
    for wrong in ("x", [["a"]] * 61, [["a"] * 31], [["a" * 201]], [[1]], ["row"]):
        bad("sql_predict", {"id": "q1", "grid": wrong})


def test_hint_fields_default_and_are_capped() -> None:
    body = validate("sql_hint", {"id": "q1"}).body
    assert body == {"id": "q1", "sql": "", "last_result": None, "history": []}
    ok = {"id": "q1", "sql": "", "history": ["Why?"] * 10}
    assert validate("sql_hint", ok).body["history"] == ["Why?"] * 10
    bad("sql_hint", {"id": "q1", "history": ["Why?"] * 11})
    bad("sql_hint", {"id": "q1", "history": [5]})
    bad("sql_hint", {"id": "q1", "history": ["x" * 501]})
    bad("sql_hint", {"id": "q1", "sql": "x" * 8001})
    bad("sql_hint", {"id": "q1", "sql": 5})
    bad("sql_hint", {"id": "q1", "last_result": "ok"})


def test_hint_last_result_keeps_only_what_a_hint_reads() -> None:
    given = {
        "ok": False,
        "match": False,
        "error": "e" * 9000,
        "columns": ["a"],
        "rows": [["r"]] * 30,
        "cell_diff": [[0, 0, "1", "2"]] * 30,
        "secret": "dropped",
        "expected_rows": [["1"]],
    }
    got = validate("sql_hint", {"id": "q1", "last_result": given}).body["last_result"]
    assert set(got) == {"ok", "match", "error", "columns", "rows", "cell_diff"}
    assert len(got["rows"]) == len(got["cell_diff"]) == 20
    assert len(got["error"]) == 8000
    wrong_types = {"ok": "yes", "error": 3, "rows": "x"}
    got = validate("sql_hint", {"id": "q1", "last_result": wrong_types})
    assert got.body["last_result"] == {}


def test_generate_needs_a_known_topic_and_defaults_the_difficulty() -> None:
    assert validate("sql_generate", {"topic": "window"}).body == {
        "topic": "window",
        "difficulty": "medium",
    }
    hard = validate("sql_generate", {"topic": "pivot", "difficulty": "hard"})
    assert hard.body["difficulty"] == "hard"
    bad("sql_generate", {"topic": "cooking"})
    bad("sql_generate", {})
    bad("sql_generate", {"topic": "pivot", "difficulty": "insane"})


def test_lesson_turn_fields() -> None:
    assert validate("sql_lesson_turn", {"topic": "basics"}).body == {
        "topic": "basics",
        "lesson_id": None,
        "answer": None,
    }
    full = {"topic": "dates", "lesson_id": "0123456789ab", "answer": " x "}
    assert validate("sql_lesson_turn", full).body == full
    for wrong in (
        {"topic": "cooking"},
        {"topic": "basics", "lesson_id": "XYZ"},
        {"topic": "basics", "lesson_id": "0123456789abc"},
        {"topic": "basics", "answer": "  "},
        {"topic": "basics", "answer": "x" * 2001},
        {"topic": "basics", "answer": 5},
    ):
        bad("sql_lesson_turn", wrong)
