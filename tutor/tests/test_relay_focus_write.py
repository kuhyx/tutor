# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``focus_event`` / ``focus_create`` / ``focus_end`` chat kinds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay.errors import RequestError
from tutor.tests._focus_support import (
    CREATE,
    CREATED,
    HOUR_MS,
    NOW,
    TODAY,
    call,
    day,
    install_fake_fp,
    project,
)

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    return install_fake_fp(monkeypatch)


def _event(ts: int, event: str = "checkin") -> dict[str, Any]:
    return {"event": event, "ts": ts, "platform": "phone"}


def test_an_event_keeps_the_client_time_and_returns_the_status(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3)]
    fp.minutes = 7
    got = call("focus_event", _event(CREATED - 90_000, "start"))
    assert fp.activity == [
        {"source": "timer", "kind": "start", "ts": NOW - 90.0, "dev": "phone"}
    ]
    assert got == {
        "name": "Now",
        "minutes": 7,
        "carry_out": 0,
        "unbacked_minutes": 0,
        "daily_minutes": 60,
        "unlock_minutes": 10,
        "ends": day(3).isoformat(),
        "replaces": ["tutor"],
    }


def test_an_event_returns_unbacked_minutes(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3)]
    fp.unbacked = 9
    assert call("focus_event", _event(CREATED))["unbacked_minutes"] == 9


def test_an_event_defaults_unbacked_minutes_to_zero(fp: FakeFp) -> None:
    fp.projects = [project("now", 0, 3)]
    assert call("focus_event", _event(CREATED))["unbacked_minutes"] == 0


def test_an_event_with_no_project_returns_a_null_name(fp: FakeFp) -> None:
    got = call("focus_event", _event(CREATED))
    assert got["name"] is None
    assert len(fp.activity) == 1


def test_a_future_ts_is_clamped_to_the_request_time(fp: FakeFp) -> None:
    call("focus_event", _event(CREATED + 5 * HOUR_MS))
    assert fp.activity[0]["ts"] == NOW


def test_a_ts_older_than_48_hours_is_refused_and_48_hours_pass(fp: FakeFp) -> None:
    with pytest.raises(RequestError) as caught:
        call("focus_event", _event(CREATED - 48 * HOUR_MS - 1))
    assert caught.value.code == "bad_request"
    assert fp.activity == []
    call("focus_event", _event(CREATED - 48 * HOUR_MS))
    assert len(fp.activity) == 1


def test_an_event_registry_failure_is_a_retryable_worker_error(fp: FakeFp) -> None:
    fp.boom = OSError("disk")
    with pytest.raises(RequestError) as caught:
        call("focus_event", _event(CREATED))
    assert (caught.value.code, caught.value.retry) == ("worker_error", True)


# ---- focus_create / focus_end ---------------------------------------------


def test_create_passes_the_fields_and_returns_the_id(fp: FakeFp) -> None:
    got = call("focus_create", CREATE)
    made = fp.projects[0]
    assert got == {"id": made.id}
    assert made.id == "exam-prep"
    assert (made.name, made.start, made.end) == ("Exam prep", day(0), day(5))
    assert (made.replaces, made.daily_minutes, made.unlock_minutes) == (
        ("leetcode", "reading"), 120, 30,
    )  # fmt: skip
    assert (made.subjects, made.site_patterns) == (("sql",), ("leetcode.com",))


def test_create_stores_the_work_url_or_leaves_it_empty(fp: FakeFp) -> None:
    call("focus_create", {k: v for k, v in CREATE.items() if k != "work_url"})
    assert fp.projects[0].work_url == ""
    url = "https://www.hackerrank.com/dashboard"
    call(
        "focus_create",
        {
            **CREATE,
            "name": "Later",
            "start": "2027-02-01",
            "end": "2027-02-03",
            "work_url": url,
        },
    )
    assert fp.projects[1].work_url == url


def test_create_ids_are_ascii_slugs_made_unique(fp: FakeFp) -> None:
    first = call("focus_create", {**CREATE, "name": "Żółć -- SQL!"})["id"]
    assert first == "zoc-sql"
    fp.projects.clear()  # no overlap now, but the id is still taken by a past one
    fp.projects.append(project("zoc-sql", -90, -80))
    again = call("focus_create", {**CREATE, "name": "Żółć -- SQL!"})["id"]
    assert again == "zoc-sql-2"
    odd = call(
        "focus_create",
        {**CREATE, "name": "???", "start": "2027-03-01", "end": "2027-03-02"},
    )
    assert odd["id"] == "project"


def test_create_conflict_is_focus_refused_without_retry(fp: FakeFp) -> None:
    fp.projects = [project("busy", 0, 9)]
    with pytest.raises(RequestError) as caught:
        call("focus_create", CREATE)
    err = caught.value
    assert (err.code, err.retry) == ("focus_refused", False)
    assert "overlaps" in err.message


def test_end_calls_end_project_with_today_or_the_day(fp: FakeFp) -> None:
    fp.projects = [project("now", -1, 5)]
    assert call("focus_end", {"id": "now"}) == {}
    assert fp.projects[0].ended_on == TODAY
    assert call("focus_end", {"id": "now", "day": day(2).isoformat()}) == {}
    assert fp.projects[0].ended_on == day(2)


def test_end_in_the_past_is_refused_and_leaves_the_project(fp: FakeFp) -> None:
    """A retroactive end would erase yesterday's shortfall and lift the lock."""
    fp.projects = [project("now", -3, 5)]
    with pytest.raises(RequestError) as caught:
        call("focus_end", {"id": "now", "day": day(-1).isoformat()})
    assert (caught.value.code, caught.value.retry) == ("focus_refused", False)
    assert "past" in caught.value.message
    assert fp.projects[0].ended_on is None
    assert call("focus_end", {"id": "now", "day": TODAY.isoformat()}) == {}
    assert fp.projects[0].ended_on == TODAY


def test_end_of_an_unknown_project_is_focus_refused(fp: FakeFp) -> None:
    with pytest.raises(RequestError) as caught:
        call("focus_end", {"id": "ghost"})
    assert caught.value.code == "focus_refused"
    assert "ghost" in caught.value.message
    fp.boom = ValueError("already ended")
    with pytest.raises(RequestError) as again:
        call("focus_end", {"id": "ghost"})
    assert again.value.message == "already ended"
