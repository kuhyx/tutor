# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""App reviews (phone / desktop offline Review) paid as tutor minutes."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest

from tutor import credit, drill, ledger_pay, review_credit
from tutor.clock import BlockReady
from tutor.curriculum.eventlog import EventLog
from tutor.ledger_io import default_paths, read_key, read_rows
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import PHONE, WORKER, engine, wiring

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

ZONE = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=ZONE).timestamp()
DESK = "5f0c1a2b-3c4d-4e5f-8a9b-0c1d2e3f4a5b"


@pytest.fixture(autouse=True)
def _warsaw(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Local time is Warsaw for the test, and whatever it was afterwards."""
    monkeypatch.setenv("TZ", "Europe/Warsaw")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def at(day: int, hh: int, mm: int, ss: int = 0) -> int:
    """Unix ms of 2026-10-``day`` hh:mm:ss in Warsaw."""
    return int(datetime(2026, 10, day, hh, mm, ss, tzinfo=ZONE).timestamp() * 1000)


_N = iter(range(10_000))


def rev(dev: str, when: int, dur: int | None, kind: str = "review") -> dict[str, Any]:
    """A logged event of ``dev`` answered at ``when`` after ``dur`` ms."""
    eid = f"01M4RBCX52MMHCK7K73E6K{next(_N):04d}"
    event: dict[str, Any] = {
        "dev": dev,
        "eid": eid,
        "k": kind,
        "s": "car",
        "c": "a-1",
        "at": when,
        "rev": 1,
    }
    if kind == "review":
        event["r"] = 3
    if dur is not None:
        event["dur_ms"] = dur
    return event


def fake_log() -> list[dict[str, Any]]:
    """Phone, desktop-app and drill (the worker's own) reviews, out of order."""
    return [
        # Phone today: 30 + 40 + 0 (< 3 s) + 60 (90 clamped) + 50 = 180 s.
        rev(PHONE, at(15, 10, 3, 32), 50_000),
        rev(PHONE, at(15, 10, 0, 30), 30_000),
        rev(PHONE, at(15, 10, 2, 42), 90_000),
        rev(PHONE, at(15, 10, 1, 10), 40_000),
        rev(PHONE, at(15, 10, 1, 12), 2_000),
        rev(PHONE, at(15, 10, 4, 0), None),  # no duration: nothing
        rev(PHONE, at(15, 10, 5, 0), 60_000, kind="flag"),  # not a review
        # Desktop app today: 45 + 45 = 90 s -> 1 minute.
        rev(DESK, at(15, 11, 0, 45), 45_000),
        rev(DESK, at(15, 11, 1, 30), 45_000),
        # The PC drill (worker's own device): already credited by drill.py.
        rev(WORKER, at(15, 9, 0, 50), 50_000),
        rev(WORKER, at(15, 9, 1, 40), 50_000),
        rev(WORKER, at(15, 9, 2, 30), 50_000),
        # Phone yesterday 23:59: pays yesterday; two days ago: out of reach.
        rev(PHONE, at(14, 23, 59, 30), 60_000),
        rev(PHONE, at(13, 12, 0, 0), 60_000),
    ]


def review_rows() -> dict[str, dict[str, Any]]:
    """The ledger's verified ``review-`` rows, by entry id."""
    where = default_paths()
    key = read_key(where.key_file)
    assert key is not None
    rows = read_rows(where.ledger) if where.ledger.exists() else []
    paying = ledger_pay.paying(rows, key)
    return {
        r["entry_id"]: r
        for r in rows
        if isinstance(r, dict)
        and str(r["entry_id"]).startswith("review-")
        and r["entry_id"] in paying
    }


def log_of(tmp_path: Path, events: list[dict[str, Any]]) -> EventLog:
    log = EventLog(tmp_path / "data")
    log.append(events)
    return log


def test_app_reviews_pay_minutes_by_day_and_device(tmp_path: Path) -> None:
    log = log_of(tmp_path, fake_log())
    review_credit.credit_pass(log, WORKER, NOW)
    rows = review_rows()
    phone, desk = f"review-20261015-{PHONE}", f"review-20261015-{DESK}"
    yesterday = f"review-20261014-{PHONE}"
    assert set(rows) == {f"{phone}-m3", f"{desk}-m1", f"{yesterday}-m1"}
    assert rows[f"{phone}-m3"]["detail"]["minutes"] == 3
    # Anchored to the review that completed the minute, never the sync time.
    assert rows[f"{phone}-m3"]["detail"]["ended_at"] == at(15, 10, 3, 32) / 1000
    assert rows[f"{phone}-m3"]["day"] == "2026-10-15"
    assert rows[f"{desk}-m1"]["detail"]["ended_at"] == at(15, 11, 1, 30) / 1000
    assert rows[f"{yesterday}-m1"]["day"] == "2026-10-14"
    assert not any(WORKER in e for e in rows)  # drill reviews never re-paid


def test_rerun_pays_nothing_new_and_a_later_review_pays_only_its_minute(
    tmp_path: Path,
) -> None:
    log = log_of(tmp_path, fake_log())
    review_credit.credit_pass(log, WORKER, NOW)
    before = read_rows(default_paths().ledger)
    assert review_credit.credit_pass(log, WORKER, NOW + 60) == []
    assert read_rows(default_paths().ledger) == before
    log.append([rev(PHONE, at(15, 10, 30, 0), 60_000)])  # 240 s -> minute 4
    review_credit.credit_pass(log, WORKER, NOW + 120)
    new = set(review_rows()) - {r["entry_id"] for r in before if isinstance(r, dict)}
    assert new == {f"review-20261015-{PHONE}-m4"}
    assert review_rows()[f"review-20261015-{PHONE}-m4"]["detail"]["minutes"] == 1


def test_daily_cap_is_shared_with_tutor_session_minutes(tmp_path: Path) -> None:
    tutor_min = ledger_pay.DAILY_CAP_MINUTES - 2
    receipt = credit.credit_span(
        BlockReady(tutor_min, 60.0 * tutor_min, NOW - 3600, 1, 1),
        tutor_min,
        "s-tutor",
        now=NOW - 3600,
    )
    assert receipt.recorded
    review_credit.credit_pass(log_of(tmp_path, fake_log()), WORKER, NOW)
    today = sum(
        r["detail"]["minutes"]
        for r in review_rows().values()
        if r["day"] == "2026-10-15"
    )
    assert today == 2  # 4 minutes earned, 2 of room left under the cap
    _, lo, hi = credit.local_day(NOW)
    where = default_paths()
    key = read_key(where.key_file)
    assert key is not None
    paid = ledger_pay.paying(read_rows(where.ledger), key)
    assert ledger_pay.minutes_between(paid, lo, hi) == ledger_pay.DAILY_CAP_MINUTES


def test_an_undone_review_is_never_paid() -> None:
    wrong = rev(PHONE, at(15, 10, 0, 0), 60_000)
    redo = rev(PHONE, at(15, 10, 0, 40), 30_000)
    undo = {**rev(PHONE, at(15, 10, 0, 30), None, "review_undo"), "of": wrong["eid"]}
    assert review_credit.units_by_session([wrong, redo], WORKER, NOW)
    assert review_credit.units_by_session([wrong, undo, redo], WORKER, NOW) == {}
    stray = {**undo, "of": "01M4RBCX52MMHCK7K73E6K9999"}  # unknown eid: no-op
    paid = review_credit.units_by_session([wrong, stray, redo], WORKER, NOW)
    assert len(paid[f"review-20261015-{PHONE}"]) == 1


def test_without_own_device_nothing_is_paid(tmp_path: Path) -> None:
    """Fail closed: drill reviews cannot be told apart, so none are credited."""
    assert review_credit.credit_pass(log_of(tmp_path, fake_log()), "", NOW) == []
    assert review_rows() == {}


def test_units_follow_the_drill_rules() -> None:
    assert review_credit.MIN_REVIEW_SECONDS == drill.MIN_PICK_SECONDS
    found = review_credit.units_by_session(fake_log(), WORKER, NOW)
    phone = found[f"review-20261015-{PHONE}"]
    assert [u.block for u in phone] == [1, 2, 3]
    assert [u.ended_at * 1000 for u in phone] == [
        at(15, 10, 1, 10),
        at(15, 10, 2, 42),
        at(15, 10, 3, 32),
    ]
    assert phone[-1].active_seconds == 180.0
    assert f"review-20261013-{PHONE}" not in found
    assert all(WORKER not in s for s in found)


def test_sync_credits_a_pulled_phone_review(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    sync_now = at(15, 12, 0) / 1000
    sync = CurriculumSync(wiring(fake, eng, now=lambda: sync_now))
    event = rev(PHONE, at(15, 11, 0, 0), 60_000)
    body = {k: v for k, v in event.items() if k not in {"dev", "eid"}}
    fake.set(f"tutor/v1/log/{PHONE}/{event['eid']}", body)

    async def go() -> None:
        await sync.sync()
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    assert set(review_rows()) == {f"review-20261015-{PHONE}-m1"}


def test_credit_now_logs_an_unreadable_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    eng, _ = engine(tmp_path)
    eng.ctx.log.path.write_text("{not json\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="tutor.review_credit"):
        assert review_credit.credit_now(eng.ctx, NOW) == []
    assert "app review credit skipped" in caplog.text
    assert review_rows() == {}
