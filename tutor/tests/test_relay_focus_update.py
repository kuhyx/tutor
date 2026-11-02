# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``focus_update`` chat kind: edit a project, refusals as focus_refused."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay.errors import RequestError
from tutor.tests._focus_support import (
    CREATE,
    TODAY,
    call,
    day,
    install_fake_fp,
    project,
    validate,
)

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp

UPDATE: dict[str, Any] = {"id": "now", **CREATE, "name": "Renamed", "end": "2027-01-18"}


def bad(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        validate(kind, body)
    return caught.value


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    return install_fake_fp(monkeypatch)


def test_update_passes_every_field_and_today(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3)]
    assert call("focus_update", UPDATE) == {
        "id": "now",
        "effective_from": TODAY.isoformat(),
    }
    edited = fp.projects[0]
    assert (edited.id, edited.name, edited.start, edited.end) == (
        "now", "Renamed", day(0), day(3),
    )  # fmt: skip
    assert (edited.replaces, edited.daily_minutes, edited.unlock_minutes) == (
        ("leetcode", "reading"), 120, 30,
    )  # fmt: skip
    assert (edited.subjects, edited.site_patterns) == (("sql",), ("leetcode.com",))
    assert fp.updated_on == TODAY


def test_absent_lists_clear_them(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3, subjects=("sql",))]
    lean = {k: v for k, v in UPDATE.items() if k not in {"subjects", "site_patterns"}}
    call("focus_update", lean)
    assert fp.projects[0].subjects == ()
    assert fp.projects[0].site_patterns == ()


def test_unknown_project_and_overlap_are_focus_refused(fp: FakeFp) -> None:
    with pytest.raises(RequestError) as unknown:
        call("focus_update", UPDATE)
    assert (unknown.value.code, unknown.value.retry) == ("focus_refused", False)
    assert "unknown project" in unknown.value.message
    fp.projects = [project("now", 0, 3), project("later", 2, 9, created=2)]
    with pytest.raises(RequestError) as clash:
        call("focus_update", UPDATE)
    assert clash.value.code == "focus_refused"
    assert "overlaps" in clash.value.message


def test_registry_failure_is_a_retryable_worker_error(fp: FakeFp) -> None:
    fp.boom = OSError("disk")
    with pytest.raises(RequestError) as caught:
        call("focus_update", UPDATE)
    assert (caught.value.code, caught.value.retry) == ("worker_error", True)


def test_update_body_is_a_create_body_plus_an_id() -> None:
    assert validate("focus_update", UPDATE).body == UPDATE
    assert bad("focus_update", {k: v for k, v in UPDATE.items() if k != "id"}).code == (
        "bad_request"
    )
    assert bad("focus_update", {**UPDATE, "id": "Bad Id"}).code == "bad_request"
    assert bad("focus_update", {**UPDATE, "daily_minutes": 0}).code == "bad_request"


def test_work_url_is_set_kept_when_absent_and_cleared_when_empty(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3)]
    url = "https://www.hackerrank.com/dashboard"
    call("focus_update", {**UPDATE, "work_url": url})
    assert fp.projects[0].work_url == url
    older = {k: v for k, v in UPDATE.items() if k != "work_url"}
    call("focus_update", older)  # a client that never heard of work_url
    assert fp.projects[0].work_url == url
    call("focus_update", {**UPDATE, "work_url": ""})
    assert fp.projects[0].work_url == ""


def test_a_deferred_edit_says_it_applies_tomorrow(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3)]
    fp.defer = True
    got = call("focus_update", UPDATE)
    assert got["effective_from"] == day(1).isoformat()
    assert day(1).isoformat() in got["message"]
    assert "today" in got["message"]
