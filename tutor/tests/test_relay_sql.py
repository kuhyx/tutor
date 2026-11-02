# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The model-free ``sql_*`` kinds: list, get, run, predict and the heartbeat."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from tutor import focus_hook
from tutor.relay import sql
from tutor.relay.errors import RequestError
from tutor.tests._sql_support import (
    EngineError,
    FakeSd,
    call,
    install_fake_fp,
    install_fake_sd,
)

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp


@pytest.fixture
def sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    return install_fake_sd(monkeypatch)


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    return install_fake_fp(monkeypatch)


def refused(kind: str, body: dict[str, object]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        call(kind, body)
    return caught.value


def test_list_turns_dataclass_metas_into_plain_dicts_and_names_the_topics(
    sd: FakeSd,
) -> None:
    got = call("sql_list", {})
    assert [d["id"] for d in got["drills"]] == ["q1", "g1"]
    assert got["drills"][1] == {
        "id": "g1",
        "title": "Mine",
        "topic": "pivot",
        "kind": "write",
        "source": "generated",
    }
    assert got["topics"][0] == "basics"
    assert "window" in got["topics"]
    assert ("ensure_running", None) not in sd.calls  # a list needs no container


def test_get_starts_the_engine_and_cuts_long_tables(sd: FakeSd) -> None:
    got = call("sql_get", {"id": "q1"})
    assert sd.calls[0] == ("ensure_running", None)
    assert got["meta"]["id"] == "q1"
    assert got["task_md"] == "List every customer."
    rows = got["tables"]["c"]["rows"]
    assert len(rows) == 200
    assert got["tables"]["c"]["truncated"] is True
    assert "truncated" not in got
    assert "reference" not in str(got).lower()


def test_get_of_an_unknown_drill_is_bad_request(sd: FakeSd) -> None:
    err = refused("sql_get", {"id": "nope"})
    assert err.code == "bad_request"
    assert "unknown drill" in err.message
    assert "nope" in err.message


def test_run_returns_the_result_and_beats_the_focus_heart(
    sd: FakeSd, fp: FakeFp
) -> None:
    got = call("sql_run", {"id": "q1", "sql": "SELECT 1"})
    assert got == {"ok": True, "match": True, "rows": [["1"]]}
    assert sd.calls[:2] == [("ensure_running", None), ("run", ("q1", "SELECT 1"))]
    assert [(a["source"], a["kind"]) for a in fp.activity] == [
        ("sql_drills", "heartbeat")
    ]


def test_a_user_sql_error_is_a_successful_request(sd: FakeSd, fp: FakeFp) -> None:
    sd.run_result = {"ok": False, "error": "syntax error near 'SELEC'", "rows": []}
    got = call("sql_run", {"id": "q1", "sql": "SELEC 1"})
    assert got["ok"] is False
    assert "syntax" in got["error"]
    assert len(fp.activity) == 1  # trying counts as work


def test_run_cuts_long_lists_and_says_so(sd: FakeSd, fp: FakeFp) -> None:
    sd.run_result = {
        "ok": True,
        "rows": [["x"]] * 250,
        "cell_diff": [[0, 0, "a", "b"]] * 600,
        "columns": ["a"],
    }
    got = call("sql_run", {"id": "q1", "sql": "SELECT 1"})
    assert (len(got["rows"]), len(got["cell_diff"])) == (200, 500)
    assert got["columns"] == ["a"]
    assert got["truncated"] is True


def test_predict_checks_the_grid_and_turns_tuples_into_lists(
    sd: FakeSd, fp: FakeFp
) -> None:
    got = call("sql_predict", {"id": "q1", "grid": [["1"]]})
    assert got == {
        "match": False,
        "cell_diff": [[0, 0, "1", "2"]],
        "actual_rows": [["2"]],
    }
    assert ("check_prediction", ("q1", [["1"]])) in sd.calls
    assert [a["source"] for a in fp.activity] == ["sql_drills"]
    call("sql_predict", {"id": "q1"})
    assert ("check_prediction", ("q1", [])) in sd.calls


def test_a_failed_run_is_no_activity(sd: FakeSd, fp: FakeFp) -> None:
    sd.boom = EngineError("docker: no daemon")
    err = refused("sql_run", {"id": "q1", "sql": "SELECT 1"})
    assert (err.code, err.retry) == ("worker_error", True)
    assert "docker: no daemon" in err.message
    assert fp.activity == []


def test_an_engine_that_times_out_is_a_retryable_worker_error(sd: FakeSd) -> None:
    sd.boom = TimeoutError("mysql did not start")
    err = refused("sql_get", {"id": "q1"})
    assert (err.code, err.retry) == ("worker_error", True)


def test_a_broken_heartbeat_never_fails_the_run(
    sd: FakeSd, fp: FakeFp, caplog: pytest.LogCaptureFixture
) -> None:
    fp.boom = OSError("registry locked")
    assert call("sql_run", {"id": "q1", "sql": "SELECT 1"})["ok"] is True
    assert "sql heartbeat skipped" in caplog.text


def test_a_missing_focus_project_skips_the_heartbeat(
    sd: FakeSd, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(focus_hook, "load_fp", lambda: None)
    assert call("sql_run", {"id": "q1", "sql": "SELECT 1"})["ok"] is True


def test_without_the_package_the_worker_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    err = refused("sql_list", {})
    assert err.code == "worker_error"
    assert "sql_drills" in err.message


def test_load_sd_imports_the_package_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(importlib, "import_module", lambda name: sentinel)
    assert sql.load_sd() is sentinel


def test_a_missing_cell_in_a_diff_is_an_empty_string_not_null(
    sd: FakeSd, fp: FakeFp
) -> None:
    sd.run_result = {"ok": True, "cell_diff": [[1, 0, "East", None], (2, 1, None, "x")]}
    got = call("sql_run", {"id": "q1", "sql": "SELECT 1"})
    assert got["cell_diff"] == [[1, 0, "East", ""], [2, 1, "", "x"]]
