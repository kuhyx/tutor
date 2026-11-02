# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``focus_status`` chat kind and the missing-package case."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor import focus_hook
from tutor.relay.errors import RequestError
from tutor.tests._focus_support import TODAY, call, day, install_fake_fp, project

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    return install_fake_fp(monkeypatch)


def test_status_without_projects(fp: FakeFp) -> None:
    got = call("focus_status", {})
    assert got["day"] == TODAY.isoformat()
    assert (got["active"], got["projects"]) == (None, [])
    assert got["subjects"] == [
        {"id": "sql", "title": "SQL"},
        {"id": "go", "title": "GO"},
    ]


def test_status_gates_mark_what_a_project_can_replace(fp: FakeFp) -> None:
    gates = {g["id"]: g for g in call("focus_status", {})["gates"]}
    assert {"workout", "leetcode", "reading", "tutor"} <= set(gates)
    for gate_id, gate in gates.items():
        assert gate["replaceable"] is (gate_id in {"leetcode", "reading", "tutor"})
        assert isinstance(gate["label"], str)


def test_status_lists_the_active_project_and_all_newest_first(fp: FakeFp) -> None:
    fp.minutes = 42
    fp.projects = [
        project("old", -30, -20, created=1),
        project(
            "now",
            -1,
            3,
            created=2,
            subjects=("sql",),
            site_patterns=("a.com",),
            work_url="https://a.com/x",
        ),
        project("next", 10, 12, created=3),
    ]
    got = call("focus_status", {})
    assert [p["id"] for p in got["projects"]] == ["next", "now", "old"]
    assert got["active"] == {
        "id": "now",
        "name": "Now",
        "start": day(-1).isoformat(),
        "end": day(3).isoformat(),
        "days_left": 4,
        "replaces": ["tutor"],
        "daily_minutes": 60,
        "unlock_minutes": 10,
        "subjects": ["sql"],
        "site_patterns": ["a.com"],
        "work_url": "https://a.com/x",
        "minutes": 42,
    }
    assert "minutes" not in got["projects"][1]
    assert [p["days_left"] for p in got["projects"]] == [3, 4, 0]


def test_an_early_ended_project_reports_its_last_day(fp: FakeFp) -> None:
    fp.projects = [project("cut", -2, 9, ended_on=day(1))]
    got = call("focus_status", {})
    assert (got["active"]["end"], got["active"]["days_left"]) == (
        day(1).isoformat(),
        2,
    )


def test_status_registry_failure_is_a_retryable_worker_error(fp: FakeFp) -> None:
    fp.boom = ValueError("projects overlap")
    with pytest.raises(RequestError) as caught:
        call("focus_status", {})
    assert (caught.value.code, caught.value.retry) == ("worker_error", True)


def test_without_the_package_every_kind_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(focus_hook, "load_fp", lambda: None)
    for kind, body in (("focus_status", {}), ("focus_end", {"id": "x"})):
        with pytest.raises(RequestError) as caught:
            call(kind, body)
        assert caught.value.code == "worker_error"
        assert "focus_project" in str(caught.value)
