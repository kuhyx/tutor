# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``mock`` kind end to end over fakes (real sandbox for code)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay import mock_mcq, mock_store
from tutor.relay.errors import RequestError
from tutor.tests._mock_support import (
    FakeSd,
    call,
    install,
    model,
    needs_bwrap,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = needs_bwrap
SUBSEQ = (
    "def longest_palindrome_subseq(s):\n    n = len(s)\n"
    "    dp = [[0] * n for _ in range(n)]\n"
    "    for i in range(n - 1, -1, -1):\n        dp[i][i] = 1\n"
    "        for j in range(i + 1, n):\n"
    "            dp[i][j] = dp[i+1][j-1] + 2 if s[i] == s[j] "
    "else max(dp[i+1][j], dp[i][j-1])\n    return dp[0][n - 1]\n"
)


def _questions(n: int = 12) -> list[dict[str, Any]]:
    good = [
        {
            "topic": f"sq {i}",
            "code": f"print({i} * {i})",
            "wrong_outputs": [str(i), str(i + 1), "none"],
        }
        for i in range(2, 2 + n)
    ]
    bad = [
        {"topic": "err", "code": "1/0", "wrong_outputs": ["a", "b", "c"]},
        {"topic": "dup", "code": "print(4)", "wrong_outputs": ["4", "4", "5"]},
    ]
    return [*bad, *good]


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    fake = install(monkeypatch)
    model(monkeypatch, _questions())
    return fake


def _start(minutes: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"op": "start"}
    if minutes:
        body["minutes"] = minutes
    return call(body)


def test_start_builds_the_paper_without_leaking_keys(sd: FakeSd) -> None:
    paper = _start(45)
    tasks = paper["tasks"]
    assert [t["section"] for t in tasks] == ["py_mcq"] * 10 + ["py_code"] + ["sql"] * 3
    assert paper["minutes"] == 45
    assert paper["deadline_ms"] - paper["started_ms"] == 45 * 60_000
    assert all(len(t["options"]) == 4 for t in tasks[:10])
    wire = json.dumps(paper)
    assert "correct" not in wire
    assert "reference" not in wire
    assert "private" not in wire
    assert all(t["title"] == f"SQL task {i}" for i, t in enumerate(tasks[11:], 1))
    assert sd.saved[0]["kind"] == "write"
    assert [t["topic"] for t in tasks[11:]][1] == "pivot"
    assert len(tasks[11]["sample"]) == 5


def test_mcq_key_is_the_real_output(sd: FakeSd) -> None:
    paper = _start()
    stored = mock_store.load(paper["mock_id"])
    for pub, priv in zip(stored["tasks"][:10], stored["private"][:10], strict=True):
        shown = pub["options"][priv["key"]]
        n = int(pub["code"].split("(")[1].split(" ")[0])
        assert shown == str(n * n)


def test_model_down_uses_the_saved_bank(
    monkeypatch: pytest.MonkeyPatch, sd: FakeSd
) -> None:
    del sd

    def boom(*_: object) -> dict[str, Any]:
        msg = "down"
        raise RuntimeError(msg)

    monkeypatch.setattr(mock_mcq, "ask_model", boom)
    paper = _start()
    assert len([t for t in paper["tasks"] if t["section"] == "py_mcq"]) == 10
    assert any("Model unavailable" in n for n in paper["notes"])


def test_fresh_questions_are_cached(sd: FakeSd, tmp_path: Path) -> None:
    del sd
    _start()
    assert len(json.loads((tmp_path / "data/mock_bank.json").read_text())) == 12


def test_answer_run_finish_and_get(sd: FakeSd) -> None:
    paper = _start()
    mid = paper["mock_id"]
    stored = mock_store.load(mid)
    key = stored["private"][0]["key"]
    wrong = (key + 1) % 4
    start = paper["started_ms"]
    assert call({"op": "answer", "mock_id": mid, "task": "mq1", "answer": str(wrong),
                 "ts": start + 5})["late"] is False  # fmt: skip
    call(
        {
            "op": "answer",
            "mock_id": mid,
            "task": "mq1",
            "answer": str(key),
            "ts": start + 9,
        }
    )
    call(
        {"op": "answer", "mock_id": mid, "task": "mq2", "answer": "9", "ts": start + 9}
    )
    sd.good = "SELECT good"
    call({"op": "answer", "mock_id": mid, "task": "sq1", "answer": "SELECT good"})
    call({"op": "answer", "mock_id": mid, "task": "sq2", "answer": "BROKEN"})
    call(
        {
            "op": "answer",
            "mock_id": mid,
            "task": "pc1",
            "answer": "def f(s):\n    return 0\n",
        }
    )
    shown = call({"op": "run", "mock_id": mid, "task": "sq1", "answer": "SELECT good"})
    assert set(shown) == {"ok", "error", "columns", "rows"}
    resumed = call({"op": "get", "mock_id": mid})
    assert resumed["answers"]["mq1"] == str(key)
    assert "result" not in resumed
    result = call({"op": "finish", "mock_id": mid})
    by_id = {t["id"]: t for t in result["tasks"]}
    assert by_id["mq1"]["correct"] is True
    assert by_id["mq2"]["correct"] is False
    assert by_id["mq2"]["detail"]["chosen"] is None
    assert by_id["mq3"]["answer"] is None
    assert by_id["sq1"]["correct"] is True
    assert by_id["sq2"]["detail"]["error"] == "syntax error"
    assert by_id["sq2"]["link"] == {"kind": "lesson", "topic": by_id["sq2"]["topic"]}
    assert by_id["sq3"]["detail"] == {"error": "No answer."}
    assert by_id["pc1"]["link"]["kind"] == "coach"
    assert by_id["pc1"]["detail"]["total"] == 15
    assert result["score"] == 2
    assert result["total"] == 14
    assert result["percent"] == 14
    assert call({"op": "finish", "mock_id": mid}) == result
    assert call({"op": "get", "mock_id": mid})["result"] == result


def test_late_and_finished_answers_are_ignored(sd: FakeSd) -> None:
    del sd
    paper = _start(5)
    mid = paper["mock_id"]
    too_late = paper["deadline_ms"] + 120_000
    late = call(
        {"op": "answer", "mock_id": mid, "task": "mq1", "answer": "1", "ts": too_late}
    )
    assert late["late"] is True
    assert call({"op": "get", "mock_id": mid})["answers"] == {}
    call({"op": "finish", "mock_id": mid})
    assert call({"op": "answer", "mock_id": mid, "task": "mq1", "answer": "1"})["late"]


def test_code_task_is_graded_by_hidden_examples(sd: FakeSd) -> None:
    del sd
    paper = _start()
    mid = paper["mock_id"]
    task = next(t for t in paper["tasks"] if t["section"] == "py_code")
    name = task["starter"].split("(")[0].removeprefix("def ")
    ran = call(
        {
            "op": "run",
            "mock_id": mid,
            "task": "pc1",
            "answer": f"def {name}(s):\n    return 0\n",
        }
    )
    assert ran["ok"] is False
    assert len(ran["examples"]) == 3
    if "subsequence" in task["title"]:
        call({"op": "answer", "mock_id": mid, "task": "pc1",
              "answer": SUBSEQ.replace("longest_palindrome_subseq", name)})  # fmt: skip
        result = call({"op": "finish", "mock_id": mid})
        item = next(t for t in result["tasks"] if t["id"] == "pc1")
        assert item["correct"] is True
        assert item["detail"]["failed"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"op": "answer", "task": "mq1"},
        {"op": "answer", "mock_id": "0" * 12},
        {"op": "get"},
        {"op": "finish"},
        {"op": "run", "mock_id": "0" * 12, "task": "mq1", "answer": "x"},
    ],
)
def test_bad_requests_are_refused(sd: FakeSd, body: dict[str, Any]) -> None:
    del sd
    with pytest.raises(RequestError) as err:
        call(body)
    assert err.value.code == "bad_request"


def test_unknown_task_and_unrunnable_mcq(sd: FakeSd) -> None:
    del sd
    mid = _start()["mock_id"]
    for body in (
        {"op": "answer", "mock_id": mid, "task": "zz9", "answer": "1"},
        {"op": "run", "mock_id": mid, "task": "mq1", "answer": "1"},
    ):
        with pytest.raises(RequestError):
            call(body)
