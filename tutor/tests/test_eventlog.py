# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The event-log mirror: untrusted events cleaned, appends idempotent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum.eventlog import (
    DRILL,
    EventLog,
    parse,
    review_event,
    worker_event,
)
from tutor.curriculum.ids import ulid

if TYPE_CHECKING:
    from pathlib import Path

EID = ulid(1000, b"\0" * 10)
BASE: dict[str, Any] = {"k": "taught", "s": "car", "c": "x", "at": 1000}


@pytest.mark.parametrize(
    "raw",
    [
        "nope",
        {**BASE, "k": "other"},
        {**BASE, "at": True},
        {**BASE, "at": 0},
        {**BASE, "s": "Car"},
        {**BASE, "c": None},
        {**BASE, "k": "review", "r": 5},
        {**BASE, "k": "review"},
    ],
)
def test_parse_drops_bad_events(raw: object) -> None:
    assert parse("d", EID, raw) is None


def test_parse_needs_eid_and_dev() -> None:
    assert parse("d", "bad", BASE) is None
    assert parse("", EID, BASE) is None


def test_parse_keeps_contract_fields_only() -> None:
    review = parse("d", EID, {**BASE, "k": "review", "r": 3, "dur_ms": 5, "junk": 1})
    assert review == {
        "dev": "d",
        "eid": EID,
        "k": "review",
        "s": "car",
        "c": "x",
        "at": 1000,
        "r": 3,
        "rev": 1,
        "dur_ms": 5,
    }
    flag = parse("d", EID, {**BASE, "k": "flag", "rev": 2, "reason": "x" * 600})
    assert flag is not None
    assert (flag["rev"], len(flag["reason"])) == (2, 500)
    assert _clean({**BASE, "k": "flag"})["reason"] == ""
    assert _clean({**BASE, "session": "s1"})["session"] == "s1"
    assert "session" not in (
        parse("d", EID, {**BASE, "k": "untaught", "session": "s"}) or {}
    )


def test_parse_keeps_a_drill_source_only() -> None:
    raw = {**BASE, "k": "review", "r": 3}
    assert _clean({**raw, "src": "drill"})["src"] == "drill"
    assert "src" not in _clean({**raw, "src": "app"})  # untrusted: drill only
    assert "src" not in _clean({**BASE, "src": "drill"})  # reviews only


def test_a_drill_review_keeps_its_source_on_disk(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    ref, span = ("car", "x"), (1000, 2000)
    plain = review_event(ref, 3, dev="pc", span=span, rev=1)
    assert "src" not in plain
    event = {**plain, "src": DRILL}
    assert log.append([event]) == [event]
    assert log.read() == [event]


def test_append_is_idempotent_and_mirror_tags_device(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    assert log.read() == []
    fresh = log.mirror("phone", {EID: BASE, ulid(2000): "junk"})
    assert len(fresh) == 1
    assert log.mirror("phone", {EID: BASE}) == []
    assert log.append([{**BASE, "dev": "phone", "eid": EID}, {"dev": "x"}]) == []
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write('\n[1]\n{"dev": "x", "eid": "bad"}\n')
    assert [e["dev"] for e in log.read()] == ["phone"]


def test_worker_event() -> None:
    taught = worker_event("taught", ("car", "x"), dev="pc", at=5, session="s")
    assert taught["session"] == "s"
    assert parse("pc", taught["eid"], taught) == taught
    assert "session" not in worker_event(
        "untaught", ("car", "x"), dev="pc", at=5, session="s"
    )
    assert "session" not in worker_event("taught", ("car", "x"), dev="pc", at=5)


def _clean(raw: dict[str, Any]) -> dict[str, Any]:
    event = parse("d", EID, raw)
    assert event is not None
    return event
