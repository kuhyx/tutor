# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

import pytest

from tutor.relay import lc_checks as c
from tutor.relay.errors import RequestError
from tutor.tests._lc_support import SQL, validate

STATEMENT = SQL.statement_md


@pytest.mark.parametrize(
    ("text", "want"),
    [("req: a b", "req"), ("  SHAPE : x", "shape"), ("require it", None)],
)
def test_gate_prefix(text: str, want: str | None) -> None:
    assert c.gate_prefix(text) == want


@pytest.mark.parametrize(
    ("text", "kind", "want"),
    [
        ("```x```", "algo", True),
        ("for (i = 0; i < n; i++) {", "algo", True),
        ("I think a map helps", "algo", False),
        ("select id from t", "sql", True),
        ("select the max from the list", "algo", False),
        ("a LEFT JOIN idea", "sql", False),
    ],
)
def test_is_code(text: str, kind: str, want: bool) -> None:
    assert c.is_code(text, kind) is want


def test_output_columns_and_shape() -> None:
    assert c.output_columns(STATEMENT) == ["id", "Jan_Revenue"]
    assert c.output_columns("no tables here") == []
    assert c.output_columns("Output: 1") == []
    assert c.shape_verdict(STATEMENT, "id and jan_revenue") == ("pass", ())
    assert c.shape_verdict(STATEMENT, "just id") == ("incomplete", ("Jan_Revenue",))
    assert c.shape_verdict("nothing", "x") == ("unverified", ())


def test_ellipsis_column_is_not_a_column() -> None:
    table = "Output:\n| id | Jan | ... | Dec |\n|---|---|---|---|\n"
    assert c.output_columns(table) == ["id", "Jan", "Dec"]
    assert c.shape_verdict(table, "id Jan Dec") == ("pass", ())


def test_frustration_counts_two_confusions_in_a_row() -> None:
    assert c.frustrated("we are going in circles", 0) == (True, 0)
    assert c.frustrated("Stop.", 0) == (True, 0)
    assert c.frustrated("I don't understand", 0) == (False, 1)
    assert c.frustrated("i dont understand", 1) == (True, 0)
    assert c.frustrated("fine", 1) == (False, 0)


def test_sentences() -> None:
    assert c.sentences("One. Two? Three!") == 3
    assert c.sentences("  ") == 0


@pytest.mark.parametrize(
    ("reply", "ok"),
    [
        ("What does the lookup return?", True),
        ("Think about it.\n\nWhat is a?", True),
        ("Try it on [1, 2].", True),
        ("What? Why?", False),
        ("That is the idea.", False),
        ("", False),
        ('He said "is it?" so: What now?', True),
        ("```\nx?\n```\n\nWrite the result.", True),
    ],
)
def test_question_problem(reply: str, ok: bool) -> None:
    assert (c.question_problem(reply) is None) is ok


def test_identifiers() -> None:
    sql = c.identifiers("", STATEMENT, "sql")
    assert {"Department", "id", "revenue", "Jan_Revenue"} <= sql
    algo = c.identifiers(
        "/* hidden */\ndef twoSum(nums, target=1, *rest):\n", "", "algo"
    )
    assert algo == {"twoSum", "nums", "target", "rest"}
    assert c.identifiers("var f = function(a, bb) {}", "", "algo") == {"bb"}


def test_code_problem() -> None:
    names = {"twoSum", "nums"}
    allowed = "kuhy wrote: nums.sort()"
    assert c.code_problem("Use `nums.sort()` here", names, allowed, "algo") is None
    assert "paste" in str(c.code_problem("Try `twoSum(nums)`", names, allowed, "algo"))
    assert c.code_problem("A toy: `f(x)`", names, allowed, "algo") is None
    assert c.code_problem("Name it `nums`", names, allowed, "algo") is None
    sql = c.code_problem(
        "```sql\nSELECT id FROM Department\n```", {"Department"}, "", "sql"
    )
    assert sql is not None
    assert (
        c.code_problem("```sql\nSELECT 1 FROM dual\n```", {"Department"}, "", "sql")
        is None
    )


def test_rungs() -> None:
    assert [c.rank(r) for r in ("", None, "H0", "H3")] == [-1, -1, 0, 3]
    with pytest.raises(ValueError, match="H9"):
        c.rank("H9")
    assert c.rung_ceiling(-1, hint=1, failed=False) == 1
    assert c.rung_ceiling(-1, hint=2, failed=False) == 1
    assert c.rung_ceiling(1, hint=2, failed=False) == 3
    assert c.rung_ceiling(2, hint=2, failed=False) == 3
    assert c.rung_ceiling(1, hint=0, failed=True) == 2
    assert c.rung_ceiling(1, hint=0, failed=False) == 1
    assert c.rung_problem("", -1) is None
    assert c.rung_problem("H1", 1) is None
    assert "climbs" in str(c.rung_problem("H2", 1))
    assert "must be" in str(c.rung_problem("nope", 1))


def test_reprint_adds_what_is_referred_to() -> None:
    assert c.reprint("Think.", "x", "t") == "Think."
    out = c.reprint("Look at your query.", " SELECT 1 ", "| a |")
    assert "SELECT 1" in out
    assert "Last result" in out
    assert c.reprint("Your query ```SELECT 1``` | a |", "SELECT 1", "| a |") == (
        "Your query ```SELECT 1``` | a |"
    )
    assert c.reprint("your code?", "", "") == "your code?"


def test_fields_reject_bad_shapes() -> None:
    with pytest.raises(RequestError):
        validate("lc_turn", {"lc_id": "nothex", "text": "x"})
    with pytest.raises(RequestError):
        validate("lc_turn", {"lc_id": "a" * 12, "text": "x", "intent": "reveal"})
    with pytest.raises(RequestError):
        validate("lc_run", {"lc_id": "a" * 12, "lang": "cobol", "code": "x"})
    with pytest.raises(RequestError):
        validate("lc_open", {"lang": "mysql", "problem": "  "})
    body = validate("lc_open", {"problem": "two-sum", "lc_id": "a" * 12}).body
    assert body["intent"] if "intent" in body else body["lc_id"] == "a" * 12
    assert (
        validate("lc_turn", {"lc_id": "a" * 12, "text": "x"}).body["intent"] == "chat"
    )


def test_confirm_entries() -> None:
    entry = {"name": " XOR ", "aliases": ["^"], "properties": ["p"]}
    got = validate("lc_cards", {"lc_id": "a" * 12, "confirm": [entry]}).body
    assert got["confirm"] == [{"name": "XOR", "aliases": ["^"], "properties": ["p"]}]
    assert validate("lc_cards", {"lc_id": "a" * 12}).body["confirm"] == []
    bad = [
        {"name": "x"},
        {"name": "x", "properties": []},
        {"name": "x", "properties": ["p"], "aliases": "no"},
        "text",
    ]
    for confirm in bad:
        with pytest.raises(RequestError):
            validate("lc_cards", {"lc_id": "a" * 12, "confirm": [confirm]})
    with pytest.raises(RequestError):
        validate("lc_cards", {"lc_id": "a" * 12, "confirm": [entry] * 6})
    with pytest.raises(RequestError):
        validate("lc_cards", {"lc_id": "a" * 12, "confirm": "x"})
