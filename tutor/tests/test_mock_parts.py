# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Palindrome variants, MCQ verification, seed bank and the ``mock`` fields."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from tutor.relay import mock_mcq, mock_palin, mock_seeds
from tutor.relay.errors import RequestError
from tutor.tests._mock_support import call, needs_bwrap

_HELPERS = "".join(
    inspect.getsource(f)
    for f in (
        mock_palin.longest_substring,
        mock_palin.longest_substring_len,
        mock_palin.longest_subsequence_len,
    )
)


@needs_bwrap
@pytest.mark.parametrize("task", mock_palin.TASKS, ids=lambda t: t.key)
def test_reference_passes_and_a_stub_fails(task: mock_palin.PalinTask) -> None:
    name = task.starter.split("(")[0].removeprefix("def ")
    good = f"{_HELPERS}\ndef {name}(s):\n    return {task.ref.__name__}(s)\n"
    results = mock_palin.run(task, good, hidden=True)
    assert len(results) == len(task.visible) + len(task.hidden)
    assert all(r["ok"] for r in results)
    stub = mock_palin.run(task, f"def {name}(s):\n    return 0\n", hidden=False)
    assert not any(r["ok"] for r in stub)
    assert len(stub) == len(task.visible)


@pytest.mark.parametrize(
    ("text", "substr", "sub_len", "subseq"),
    [("babad", "bab", 3, 3), ("cbbd", "bb", 2, 2), ("a", "a", 1, 1), ("", "", 0, 0)],
)
def test_references(text: str, substr: str, sub_len: int, subseq: int) -> None:
    assert mock_palin.longest_substring(text) == substr
    assert mock_palin.longest_substring_len(text) == sub_len
    assert mock_palin.longest_subsequence_len(text) == subseq


@needs_bwrap
def test_every_seed_runs_and_has_a_real_key() -> None:
    assert len(mock_mcq.seeds()) == len(mock_seeds.SEEDS)


@needs_bwrap
@pytest.mark.parametrize(
    ("code", "wrong", "ok"),
    [
        ("print(2 + 2)", ["3", "5", "22"], True),
        ("print(2 + 2)", ["4", "5", "22"], False),
        ("print(2 + 2)", ["3", "3", "5"], False),
        ("1 / 0", ["a", "b", "c"], False),
        ("x = 1", ["a", "b", "c"], False),
        ("while True: pass", ["a", "b", "c"], False),
        ("", ["a", "b", "c"], False),
        ("print('x' * 500)", ["a", "b", "c"], False),
    ],
)
def test_verify(code: str, wrong: list[str], ok: bool) -> None:
    got = mock_mcq.verify("t", code, wrong)
    assert (got is not None) is ok
    if got:
        assert got["correct"] == "4"
        assert "4" not in got["wrong"]


@pytest.mark.parametrize(
    "body",
    [
        {"op": "nope"},
        {"op": "start", "minutes": 2},
        {"op": "start", "minutes": 999},
        {"op": "start", "minutes": "60"},
        {"op": "get", "mock_id": "XYZ"},
        {"op": "answer", "mock_id": "0" * 12, "task": "Bad Task"},
        {"op": "answer", "mock_id": "0" * 12, "task": "mq1", "answer": "x" * 9000},
        {"op": "answer", "mock_id": "0" * 12, "task": "mq1", "ts": -4},
    ],
)
def test_bad_fields_are_refused(body: dict[str, Any]) -> None:
    with pytest.raises(RequestError) as err:
        call(body)
    assert err.value.code == "bad_request"
