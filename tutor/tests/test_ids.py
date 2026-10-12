# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Ids, ULIDs, the device id and the request error."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import ids
from tutor.curriculum.errors import RequestError
from tutor.curriculum.ids import device_id, slug, ulid, valid_eid, valid_id

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("car", True),
        ("how-a-car-works", True),
        ("a" * 48, True),
        ("a" * 49, False),
        ("Car", False),
        ("a--b", False),
        ("-a", False),
        ("", False),
        (3, False),
    ],
)
def test_valid_id(value: object, ok: bool) -> None:
    assert valid_id(value) is ok


def test_slug_cuts_at_a_word_and_dedupes() -> None:
    assert slug("How a Car works?") == "how-a-car-works"
    assert slug("x", {"x", "x-2"}) == "x-3"
    long = slug(" ".join(["word"] * 30))
    assert len(long) <= 45
    assert long.endswith("word")
    assert slug("!!!", fallback="item") == "item"
    assert slug("a" * 60) == "a" * 45


def test_ulid_is_sortable_and_valid() -> None:
    first, second = ulid(1000, b"\0" * 10), ulid(1001, b"\0" * 10)
    assert valid_eid(first)
    assert first < second
    assert len(ulid(5)) == 26
    assert ulid(5, b"\1") == ulid(5, b"\1" + b"\0" * 9)
    assert not valid_eid("x")


def test_device_id_is_written_once(tmp_path: Path) -> None:
    path = tmp_path / "d" / "device_id"
    first = device_id(path)
    assert device_id(path) == first
    path.write_text("\n", encoding="utf-8")
    assert device_id(path) != first


def test_request_error_codes() -> None:
    err = RequestError("plan_conflict", "reload")
    assert isinstance(err, ValueError)
    assert err.result(5) == {
        "ok": False,
        "at": 5,
        "code": "plan_conflict",
        "error": "reload",
        "retry": False,
    }
    with pytest.raises(ValueError, match="unknown error code"):
        RequestError("nope", "x")


def test_ulid_is_monotonic_within_a_millisecond(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = ulid(10_000)
    second = ulid(10_000)
    earlier = ulid(9_000)  # a clock step back still sorts after
    assert first < second < earlier
    monkeypatch.setattr(ids, "_MONO", [20_000, ids._MAX_RAND])
    assert ulid(20_000).startswith(ulid(20_000, b"\0")[:10])
