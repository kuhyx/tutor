# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Request validation of the ``focus_*`` kinds."""

from __future__ import annotations

from typing import Any

import pytest

from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import CODES, RequestError
from tutor.tests._focus_support import CREATE, CREATED, validate


def bad(kind: str, body: dict[str, Any]) -> RequestError:
    with pytest.raises(RequestError) as caught:
        validate(kind, body)
    return caught.value


def test_the_kinds_are_chat_lane_kinds() -> None:
    for kind in (
        "focus_status",
        "focus_event",
        "focus_create",
        "focus_update",
        "focus_end",
    ):
        assert protocol.KINDS[kind][0] == protocol.CHAT
        assert kind in CHAT_HANDLERS
    assert "focus_refused" in CODES
    assert validate("focus_status", {"x": 1}).body == {}


def test_an_event_needs_a_known_event_platform_and_ms_ts() -> None:
    good = {"event": "checkin", "ts": CREATED, "platform": "phone"}
    no_card = {"subject": None, "card": None}  # only ``card`` events name one
    assert validate("focus_event", good).body == good | no_card
    card = good | {"event": "card", "subject": "sql", "card": "joins"}
    assert validate("focus_event", card).body == card
    for field, value in (
        ("subject", "Bad Id"),
        ("card", 7),
        ("event", "pause"),
        ("platform", "tablet"),
        ("ts", -1),
        ("ts", 1.5),
        ("ts", "1"),
        ("ts", None),
    ):
        assert bad("focus_event", {**good, field: value}).code == "bad_request"


def test_a_create_body_is_validated_field_by_field() -> None:
    assert validate("focus_create", CREATE).body == CREATE
    lean = {
        k: v
        for k, v in CREATE.items()
        if k not in {"replaces", "subjects", "site_patterns"}
    }
    assert validate("focus_create", lean).body["replaces"] == []
    assert validate("focus_create", lean).body["subjects"] == []
    assert validate("focus_create", lean).body["site_patterns"] == []
    wrong: list[tuple[str, Any]] = [
        ("name", ""),
        ("name", "  "),
        ("name", "x" * 81),
        ("start", "2027-1-5"),
        ("start", "2027-02-30"),
        ("end", "tomorrow"),
        ("replaces", ["workout"]),
        ("replaces", "leetcode"),
        ("daily_minutes", 0),
        ("daily_minutes", 721),
        ("daily_minutes", True),
        ("unlock_minutes", -1),
        ("unlock_minutes", 721),
        ("subjects", ["Bad Slug"]),
        ("subjects", "sql"),
        ("site_patterns", "a.com"),
        ("site_patterns", ["x" * 101]),
        ("site_patterns", ["has space.com"]),
        ("site_patterns", ["a.com"] * 21),
        ("site_patterns", [3]),
    ]
    for field, value in wrong:
        assert bad("focus_create", {**CREATE, field: value}).code == "bad_request"


def test_an_end_needs_a_slug_and_an_optional_day() -> None:
    assert validate("focus_end", {"id": "exam"}).body == {"id": "exam", "day": None}
    both = {"id": "exam", "day": "2027-01-16"}
    assert validate("focus_end", both).body == both
    assert bad("focus_end", {"id": "Bad Id"}).code == "bad_request"
    assert bad("focus_end", {"id": "exam", "day": "soon"}).code == "bad_request"


def test_work_url_is_optional_and_must_be_a_plain_http_url() -> None:
    bare = {k: v for k, v in CREATE.items() if k != "work_url"}
    assert validate("focus_create", bare).body["work_url"] is None
    url = "https://www.hackerrank.com/dashboard"
    assert validate("focus_create", {**CREATE, "work_url": url}).body["work_url"] == url
    assert (
        validate("focus_update", {"id": "a", **CREATE, "work_url": ""}).body["work_url"]
        == ""
    )
    for value in (
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://",
        "https://a b.com",
        "https://a.com/" + "x" * 2000,
        "hackerrank.com",
        3,
        ["https://a.com"],
    ):
        assert bad("focus_create", {**CREATE, "work_url": value}).code == "bad_request"
