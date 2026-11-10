# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Interview projects over the relay: create, status, trips, weekends, evidence."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from tutor.relay.errors import RequestError
from tutor.tests._fake_fp_interview import FakeInterviewFp, FakeTrip
from tutor.tests._interview_support import (
    INTERVIEW,
    NOW_LOCAL,
    call,
    install,
    interview_project,
    ms,
    naive,
)

SAT = date(2027, 1, 16)
TRIP = [{"start": "2027-01-16", "end": "2027-01-17"}]
PLAIN = INTERVIEW | {"kind": "focus", "test_at": None, "invite_url": ""}


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeInterviewFp:
    return install(monkeypatch)


def refused(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        call(kind, body)
    return caught.value


def test_create_an_interview_with_a_trip_answers_the_covered_weekend(
    fp: FakeInterviewFp,
) -> None:
    got = call("focus_create", INTERVIEW | {"trips": TRIP})
    made = fp.projects[0]
    assert got == {"id": made.id}
    assert made.kind == "interview"
    assert made.test_at == naive(2027, 1, 20, 10, 0)
    assert made.invite_url == INTERVIEW["invite_url"]
    assert made.trips == (FakeTrip(SAT, date(2027, 1, 17)),)
    assert made.weekend_answers == ((SAT, True),)


def test_create_with_no_trip_prefills_nothing(fp: FakeInterviewFp) -> None:
    call("focus_create", INTERVIEW | {"no_trip": True, "invite_url": None})
    made = fp.projects[0]
    assert (made.trips, made.weekend_answers, made.invite_url) == ((), (), "")


def test_a_trip_that_misses_every_saturday_answers_nothing(
    fp: FakeInterviewFp,
) -> None:
    trips = [{"start": "2027-01-18", "end": "2027-01-19"}]
    call("focus_create", INTERVIEW | {"trips": trips})
    assert fp.projects[0].weekend_answers == ()


@pytest.mark.parametrize(
    "extra",
    [
        {"test_at": None, "no_trip": True},
        {},  # neither trips nor no_trip
        {"no_trip": True, "trips": TRIP},
    ],
)
def test_an_interview_needs_a_test_time_and_trips_or_an_explicit_no_trip(
    fp: FakeInterviewFp, extra: dict[str, Any]
) -> None:
    assert refused("focus_create", INTERVIEW | extra).code == "bad_request"
    assert fp.projects == []


@pytest.mark.parametrize(
    "extra",
    [
        {"test_at": "2027-01-20T10:00"},
        {"invite_url": "https://x.test"},
        {"no_trip": True},
        {"trips": TRIP},
    ],
)
def test_a_focus_project_refuses_interview_fields(
    fp: FakeInterviewFp, extra: dict[str, Any]
) -> None:
    assert refused("focus_create", PLAIN | extra).code == "bad_request"
    assert fp.projects == []


def test_focus_projects_still_create_without_interview_kwargs(
    fp: FakeInterviewFp,
) -> None:
    call("focus_create", PLAIN)
    assert fp.projects[0].kind == "focus"


def test_create_refusals_are_focus_refused(fp: FakeInterviewFp) -> None:
    interview_project(fp)  # the same days are taken: overlap
    assert (
        refused("focus_create", INTERVIEW | {"no_trip": True}).code == "focus_refused"
    )


def test_status_shows_kind_milestones_and_missed(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    fp.rows = [ms("rules", "done"), ms("trip_ask:2027-01-16", "missed")]
    fp.status_extra = {"daily_minutes": 30, "unlock_minutes": 10}
    got = call("focus_status", {})
    active = got["active"]
    assert active["kind"] == "interview"
    assert active["missed"] is True
    assert active["milestones"] == [
        {"id": "rules", "due": "2027-01-16T23:59:00", "state": "done"},
        {"id": "trip_ask:2027-01-16", "due": "2027-01-16T23:59:00", "state": "missed"},
    ]
    assert (active["daily_minutes"], active["unlock_minutes"]) == (30, 10)
    assert active["test_at"] == "2027-01-20T10:00:00"
    assert active["invite_url"] == INTERVIEW["invite_url"]
    assert active["trips"] == []
    assert active["weekend_answers"] == {}
    assert got["projects"][0]["kind"] == "interview"
    assert "milestones" not in got["projects"][0]


def test_status_lists_trips_and_answers(fp: FakeInterviewFp) -> None:
    interview_project(
        fp, trips=[FakeTrip(SAT, date(2027, 1, 17), 5)], weekend_answers={SAT: True}
    )
    row = call("focus_status", {})["projects"][0]
    assert row["trips"] == [{"start": "2027-01-16", "end": "2027-01-17"}]
    assert row["weekend_answers"] == {"2027-01-16": True}
    assert ("milestones", {"project": "codility", "now": NOW_LOCAL}) in fp.calls


def test_status_of_a_focus_project_has_no_milestones(fp: FakeInterviewFp) -> None:
    call("focus_create", PLAIN)
    active = call("focus_status", {})["active"]
    assert (active["kind"], active["milestones"]) == ("focus", [])
    assert active["missed"] is False
    assert "test_at" not in active


def test_status_with_unreadable_evidence_is_a_retryable_error(
    fp: FakeInterviewFp,
) -> None:
    interview_project(fp)
    fp.milestones_error = OSError("evidence")
    got = refused("focus_status", {})
    assert (got.code, got.retry) == ("worker_error", True)


def test_evidence_taps_scores_and_slots_reach_the_registry(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    fp.rows = [ms("rules", "done")]
    cases: list[tuple[dict[str, Any], object]] = [
        ({"milestone": "phone:2027-01-16", "kind": "tap"}, None),
        ({"milestone": "mock", "kind": "score", "value": 71.5}, 71.5),
        (
            {"milestone": "slot", "kind": "slot", "value": "2027-01-19T09:00"},
            "2027-01-19T09:00",
        ),
        ({"milestone": "slot", "kind": "slot_confirm", "value": True}, True),
    ]
    for body, value in cases:
        got = call("focus_evidence", {"id": "codility", **body})
        assert got["missed"] is False
        assert got["milestones"][0]["id"] == "rules"
        name, args = fp.calls[-2]  # the call before the status read
        assert name == "record_evidence"
        assert (args["milestone"], args["kind"], args["value"]) == (
            body["milestone"],
            body["kind"],
            value,
        )
        assert args["now"] == NOW_LOCAL
        assert args["file"] is None


def test_evidence_the_registry_refuses_comes_back_loud(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    score = {"id": "x", "milestone": "mock", "kind": "score", "value": 1}
    fp.refuse = ValueError("'rules' takes evidence kinds ['file'], not 'tap'")
    got = refused("focus_evidence", score)
    assert got.code == "focus_refused"
    assert "takes evidence kinds" in got.message
    fp.refuse = KeyError("x")
    assert refused("focus_evidence", score).code == "focus_refused"
    fp.refuse = OSError("disk")
    got = refused("focus_evidence", score)
    assert (got.code, got.retry) == ("worker_error", True)
