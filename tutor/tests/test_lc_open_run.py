# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from tutor.relay import lc_backend, lc_state
from tutor.relay.errors import RequestError
from tutor.tests import _lc_support as s

s_install, s_open = s.install, s.open_session


def test_open_fetches_and_asks_the_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    fakes.replies.append(s.reply("Restated. Which part is unclear?"))
    got = s.call("lc_open", {"problem": "https://leetcode.com/problems/two-sum/"})
    assert got["reply_md"].startswith("Restated")
    assert (got["slug"], got["kind"], got["lang"], got["model"]) == (
        "two-sum",
        "algo",
        "python3",
        "sonnet",
    )
    assert got["langs"] == ["python3", "javascript", "typescript"]
    assert got["state"]["phase"] == "gate"
    assert got["state"]["gate"] == {
        "kind": "req",
        "tries": 0,
        "max": 3,
        "open": False,
        "forced": False,
    }
    assert got["state"]["turns"] == {"used": 0, "budget": 16, "over": False}
    assert fakes.events() == ["session_start"]
    assert fakes.fp.activity == [{"source": "tutor", "kind": "heartbeat"}]
    again = s.call("lc_list", {})
    assert [r["slug"] for r in again["recent"]] == ["two-sum"]
    assert [c["name"] for c in again["clusters"]] == ["palindromes-dp", "bits"]
    assert again["clusters"][0]["problems"] == [
        "longest-palindromic-subsequence",
        "longest-palindromic-substring",
        "palindromic-substrings",
        "valid-palindrome",
        "valid-palindrome-ii",
        "longest-palindrome",
        "minimum-insertion-steps-to-make-a-string-palindrome",
    ]
    assert again["due"][0]["slug"] == "two-sum"


def test_resume_returns_the_thread_without_a_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    fakes.prompts.clear()
    got = s.call("lc_open", {"lc_id": lc_id})
    assert got["thread"] == [{"mine": False, "md": "Restated. Which part?"}]
    assert "reply_md" not in got
    assert not fakes.prompts
    assert got["state"]["exit"] == {"step": "explain", "tries": 0}
    with pytest.raises(RequestError, match="unknown coach session"):
        s.call("lc_open", {"lc_id": "0" * 12})


def test_corrupt_session_file_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    path = lc_state._path(lc_id)
    path.write_text("[1]", encoding="utf-8")
    with pytest.raises(RequestError, match="unknown coach session"):
        s.call("lc_open", {"lc_id": lc_id})


def test_sql_defaults_and_language_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch, s.Fakes(problem=s.SQL))
    lc_id = s.open_session(fakes)
    assert s.stored(lc_id)["lang"] == "mysql"
    assert s.call("lc_open", {"lc_id": lc_id})["state"]["gate"]["kind"] == "shape"
    with pytest.raises(RequestError, match="not a language of this sql"):
        s.open_session(fakes, lang="python3")


def test_premium_slug_asks_for_a_paste(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch, s.Fakes(fetch_error=LookupError("x")))
    with pytest.raises(RequestError) as caught:
        s.call("lc_open", {"problem": "paid-one"})
    assert (caught.value.code, caught.value.extra) == (
        "bad_request",
        {"reason": "paste_statement"},
    )
    fakes.replies.append(s.reply("Restated. Which part?"))
    pasted = s.call(
        "lc_open", {"statement": "Do the thing.", "title": "T", "lang": "mysql"}
    )
    assert pasted["slug"].startswith("paste-")
    assert (pasted["kind"], pasted["title"]) == ("sql", "T")
    fakes.replies.append(s.reply("Restated. Which part?"))
    untitled = s.call("lc_open", {"statement": "Do another thing."})
    assert (untitled["kind"], untitled["title"]) == ("algo", "Pasted problem")


def test_open_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch, s.Fakes(fetch_error=OSError("down")))
    with pytest.raises(RequestError) as caught:
        s.call("lc_open", {"problem": "two-sum"})
    assert (caught.value.code, caught.value.retry) == ("worker_error", True)
    fakes.fetch_error = ValueError("not a LeetCode URL")
    with pytest.raises(RequestError, match="not a LeetCode URL"):
        s.call("lc_open", {"problem": "two-sum"})
    with pytest.raises(RequestError, match="needs problem"):
        s.call("lc_open", {})


def test_missing_library_is_a_worker_error(monkeypatch: pytest.MonkeyPatch) -> None:
    lc_backend.install(None, None)
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    with pytest.raises(RequestError, match="not installed") as caught:
        s.call("lc_list", {})
    assert caught.value.code == "worker_error"


def test_log_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s_install(monkeypatch)

    def boom(*args: Any, **kwargs: Any) -> None:
        msg = "disk"
        raise OSError(msg)

    lc_backend.install(dataclasses.replace(lc_backend.coach(), log=boom), fakes.run)
    assert s_open(fakes)


def test_heartbeat_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    fakes.fp.boom = RuntimeError("fp broke")
    assert s.open_session(fakes)


def test_run_is_held_until_the_gate_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    got = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    assert got["held"] is True
    assert "held back" in got["note"]
    assert not fakes.runs
    with pytest.raises(RequestError, match="not a language"):
        s.call("lc_run", {"lc_id": lc_id, "lang": "mysql", "code": "x"})


def test_run_reports_per_example_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    fakes.run_report = {
        "ok": True,
        "examples": [
            {"n": 1, "ok": True},
            {"n": 2, "ok": False, "columns": ["a"], "rows": [["1"]], "got": "1"},
        ],
    }
    got = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "def f(): 1"})
    assert (got["passed"], got["total"], got["no_examples"]) == (1, 2, False)
    state = s.stored(lc_id)
    assert (state["failed"], state["ran_ok"], state["code_seen"]) == (True, False, True)
    assert "| a |" in state["last_table"]
    assert fakes.events().count("code") == 1
    fakes.run_report = {"ok": True, "examples": [{"n": 1, "ok": True}]}
    done = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "def f(): 2"})
    assert done["state"]["ran_ok"] is True
    assert s.stored(lc_id)["runs"] == 2
    assert fakes.events().count("code") == 1


def test_run_without_examples_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    fakes.run_report = {"ok": True, "no_examples": True}
    got = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    assert (got["no_examples"], got["total"]) == (True, 0)
    assert "cannot run this problem's examples locally" in got["note"]
    assert got["state"]["ran_ok"] is False
    state = s.stored(lc_id)
    assert (state["no_examples"], state["failed"]) == (True, False)
    assert fakes.runs[-1] == ("python3", "x", s.ALGO.starter["python3"])
    fakes.run_report = {"ok": False, "error": "SyntaxError", "examples": []}
    bad = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    assert (bad["ok"], bad["error"]) == (False, "SyntaxError")
    fakes.run_error = TimeoutError("5 s")
    with pytest.raises(RequestError, match="runner failed") as caught:
        s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    assert caught.value.retry is True


def test_run_cuts_long_example_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = s.install(monkeypatch)
    lc_id = s.open_session(fakes)
    s.gated_open(fakes, lc_id)
    fakes.run_report = {
        "ok": True,
        "examples": [{"n": i, "ok": True} for i in range(210)],
    }
    got = s.call("lc_run", {"lc_id": lc_id, "lang": "python3", "code": "x"})
    assert len(got["examples"]) == 200
    assert got["truncated"] is True
    assert got["total"] == 210
