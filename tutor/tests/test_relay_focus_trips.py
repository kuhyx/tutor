# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Trips and weekend answers of an interview project over the relay."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import pytest

from tutor import focus_hook
from tutor.relay.errors import RequestError
from tutor.tests._interview_support import NOW_LOCAL, call, install, interview_project

if TYPE_CHECKING:
    from tutor.tests._fake_fp_interview import FakeInterviewFp

SAT = date(2027, 1, 16)
TRIP = [{"start": "2027-01-16", "end": "2027-01-17"}]


@pytest.fixture
def fp(monkeypatch: pytest.MonkeyPatch) -> FakeInterviewFp:
    return install(monkeypatch)


def refused(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        call(kind, body)
    return caught.value


def test_a_trip_is_added_and_the_weekends_it_covers_are_answered(
    fp: FakeInterviewFp,
) -> None:
    interview_project(fp)
    got = call("focus_trip", {"id": "codility", **TRIP[0]})
    assert got["trips"] == TRIP
    assert got["weekend_answers"] == {"2027-01-16": True}
    calls = [(n, a) for n, a in fp.calls if n in {"add_trip", "answer_weekend"}]
    assert [n for n, _ in calls] == ["add_trip", "answer_weekend"]
    assert calls[1][1]["trip"] is True
    assert calls[0][1]["now"] == NOW_LOCAL


def test_a_trip_flips_a_no_trip_answer_but_skips_one_already_true(
    fp: FakeInterviewFp,
) -> None:
    interview_project(fp, weekend_answers={SAT: False, date(2027, 1, 23): True})
    body = {"id": "codility", "start": "2027-01-16", "end": "2027-01-24"}
    call("focus_trip", body)
    answers = [a["saturday"] for n, a in fp.calls if n == "answer_weekend"]
    assert answers == [SAT]  # the 23rd was already True


def test_a_trip_outside_every_saturday_answers_nothing(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    call("focus_trip", {"id": "codility", "start": "2027-01-18", "end": "2027-01-19"})
    assert [n for n, _ in fp.calls if n == "answer_weekend"] == []


def test_a_shrinking_trip_is_refused_loudly(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    fp.refuse = ValueError("a trip may only get stricter")
    body = {"id": "codility", "start": "2027-01-17", "end": "2027-01-17"}
    got = refused("focus_trip", body)
    assert got.code == "focus_refused"
    assert "stricter" in got.message


def test_an_unknown_project_in_a_trip_is_refused(fp: FakeInterviewFp) -> None:
    fp.refuse = KeyError("nope")
    got = refused("focus_trip", {"id": "nope", **TRIP[0]})
    assert got.code == "focus_refused"


def test_a_weekend_answer_goes_to_the_registry(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    body = {"id": "codility", "saturday": "2027-01-16", "trip": False}
    got = call("focus_weekend", body)
    assert got["weekend_answers"] == {"2027-01-16": False}
    _, args = next(c for c in fp.calls if c[0] == "answer_weekend")
    assert (args["saturday"], args["trip"], args["now"]) == (SAT, False, NOW_LOCAL)


def test_flipping_a_trip_answer_back_is_refused_loudly(fp: FakeInterviewFp) -> None:
    interview_project(fp)
    fp.refuse = ValueError("a trip answer may only get stricter: it stays True")
    body = {"id": "codility", "saturday": "2027-01-16", "trip": False}
    got = refused("focus_weekend", body)
    assert got.code == "focus_refused"
    assert "stays True" in got.message


def test_the_interview_kinds_need_focus_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(focus_hook, "load_fp", lambda: None)
    assert refused("focus_trip", {"id": "x", **TRIP[0]}).code == "worker_error"
