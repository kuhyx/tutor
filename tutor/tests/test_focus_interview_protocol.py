# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request validation of the interview kinds and focus_create's interview fields."""

from __future__ import annotations

from typing import Any

import pytest

from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import RequestError
from tutor.tests._focus_support import CREATE, validate
from tutor.tests._interview_support import INTERVIEW

ULID = "01J00000000000000000000001"
SHA = "a" * 64
FILE = {
    "id": "codility",
    "milestone": "rules",
    "kind": "file",
    "upload": ULID,
    "chunks": 2,
    "sha256": SHA,
    "mime": "image/png",
}
TRIP = [{"start": "2027-01-16", "end": "2027-01-17"}]


def bad(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        validate(kind, body)
    return caught.value


def test_the_new_kinds_are_chat_lane_kinds() -> None:
    for kind in ("focus_evidence", "focus_trip", "focus_weekend"):
        assert protocol.KINDS[kind][0] == protocol.CHAT
        assert kind in CHAT_HANDLERS


def test_create_defaults_to_a_plain_focus_project() -> None:
    got = validate("focus_create", CREATE).body
    assert got["name"] == "Exam prep"  # the old fields are untouched
    assert (got["kind"], got["test_at"], got["invite_url"]) == ("focus", None, "")
    assert (got["trips"], got["no_trip"]) == ([], False)


def test_create_takes_the_interview_fields() -> None:
    got = validate("focus_create", INTERVIEW | {"trips": TRIP}).body
    assert got["kind"] == "interview"
    assert got["test_at"] == "2027-01-20T10:00"
    assert got["invite_url"] == INTERVIEW["invite_url"]
    assert got["trips"] == TRIP
    seconds = validate("focus_create", INTERVIEW | {"test_at": "2027-01-20T10:00:30"})
    assert seconds.body["test_at"] == "2027-01-20T10:00:30"
    assert validate("focus_create", INTERVIEW | {"no_trip": True}).body["no_trip"]


@pytest.mark.parametrize(
    "extra",
    [
        {"kind": "weird"},
        {"test_at": "tomorrow"},
        {"test_at": "2027-01-20"},
        {"test_at": "2027-01-20T10:00:00+01:00"},
        {"test_at": "2027-01-20T10:00+01"},
        {"test_at": "2027-02-30T10:00"},
        {"test_at": 5},
        {"invite_url": "ftp://x"},
        {"trips": "x"},
        {"trips": ["x"]},
        {"trips": [{"start": "2027-01-16"}]},
        {"trips": [{"start": "2027-01-18", "end": "2027-01-17"}]},
        {"trips": [{"start": "2027-01-16", "end": "bad"}]},
        {"trips": TRIP * 21},
        {"no_trip": "yes"},
    ],
)
def test_create_refuses_bad_interview_fields(extra: dict[str, Any]) -> None:
    assert bad("focus_create", INTERVIEW | extra).code == "bad_request"


def test_evidence_takes_each_kind_and_value() -> None:
    assert validate("focus_evidence", FILE).body == FILE | {"value": None}
    tap = {"id": "codility", "milestone": "phone:2027-01-16", "kind": "tap"}
    assert validate("focus_evidence", tap).body["value"] is None
    for value in (3, 2.5, "2027-01-20T10:00", True):
        body = {"id": "x", "milestone": "mock", "kind": "score", "value": value}
        assert validate("focus_evidence", body).body["value"] == value
    absent = validate(
        "focus_evidence", {"id": "x", "milestone": "rules", "kind": "tap"}
    )
    assert absent.body["upload"] is None
    assert absent.body["chunks"] is None


@pytest.mark.parametrize(
    "extra",
    [
        {"id": "../x"},
        {"milestone": "../x"},
        {"milestone": "Rules"},
        {"milestone": "x" * 41},
        {"kind": "delete"},
        {"value": [1]},
        {"value": "x" * 41},
        {"value": float("inf")},
        {"upload": "nope"},
        {"upload": 5},
        {"chunks": 0},
        {"chunks": 17},
        {"chunks": True},
        {"sha256": "abc"},
        {"sha256": "G" * 64},
        {"mime": "image/gif"},
        {"mime": 5},
    ],
)
def test_evidence_refuses_a_bad_field(extra: dict[str, Any]) -> None:
    assert bad("focus_evidence", FILE | extra).code == "bad_request"


def test_trip_and_weekend_shapes() -> None:
    trip = {"id": "codility", "start": "2027-01-16", "end": "2027-01-17"}
    assert validate("focus_trip", trip).body == trip
    weekend = {"id": "codility", "saturday": "2027-01-16", "trip": False}
    assert validate("focus_weekend", weekend).body == weekend
    assert bad("focus_trip", trip | {"end": "x"}).code == "bad_request"
    assert bad("focus_weekend", weekend | {"trip": "no"}).code == "bad_request"
    assert bad("focus_weekend", weekend | {"saturday": "x"}).code == "bad_request"
