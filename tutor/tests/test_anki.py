# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Anki reviews in an unavailability window paid as tutor minutes (``anki``)."""

from __future__ import annotations

from datetime import datetime
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest

from tutor import anki, credit, unavailable
from tutor.anki_collection import COLLECTION_ENV, AnkiError
from tutor.ledger_io import default_paths, read_rows
from tutor.tests._anki_support import append, make_collection

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

ZONE = ZoneInfo("Europe/Warsaw")
NOON = datetime(2026, 10, 15, 12, 0, tzinfo=ZONE).timestamp()
YESTERDAY_2350 = datetime(2026, 10, 14, 23, 50, tzinfo=ZONE).timestamp()


@pytest.fixture(autouse=True)
def _warsaw(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Local time is Warsaw for the test, and whatever it was afterwards."""
    monkeypatch.setenv("TZ", "Europe/Warsaw")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def collection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "anki/collection.anki2"
    monkeypatch.setenv(COLLECTION_ENV, str(path))
    return path


def ms(ts: float) -> int:
    return int(ts * 1000)


def window(start: float, end: float) -> None:
    unavailable.path().parent.mkdir(parents=True, exist_ok=True)
    line = {"start": int(start), "end": int(end), "reason": "rate_limit"}
    with unavailable.path().open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")


def anki_rows() -> list[dict[str, Any]]:
    return [
        r
        for r in read_rows(default_paths().ledger)
        if isinstance(r, dict) and str(r.get("entry_id")).startswith("anki-")
    ]


def test_units_count_only_reviews_in_a_window() -> None:
    windows = [unavailable.Window(100, 200, "network")]
    found = [
        (ms(50), 120_000),  # before the window: ignored
        (ms(110), 90_000),  # 1.5 min
        (ms(120), -5),  # a negative time adds nothing
        (ms(130), 100_000),  # total 190 s: minutes 2 and 3 end here
        (ms(250), 60_000),  # after: ignored
    ]
    got = anki.units(found, windows)
    assert [(u.block, u.ended_at, u.active_seconds) for u in got] == [
        (1, 110.0, 90.0),
        (2, 130.0, 190.0),
        (3, 130.0, 190.0),
    ]


def test_a_pass_pays_new_minutes_once(collection: Path) -> None:
    window(NOON - 3600, NOON + 3600)
    make_collection(
        collection,
        [(ms(NOON - 7200), 600_000, 1), (ms(NOON - 60), 150_000, 1)],
        keep_wal=True,
    )
    first = anki.credit_pass(NOON)
    assert (first.day, first.eligible_min) == ("2026-10-15", 2)
    assert [r["entry_id"] for r in first.rows] == ["anki-2026-10-15-m2"]
    assert anki.credit_pass(NOON).rows == []  # idempotent
    append(collection, [(ms(NOON + 10), 40_000, 1), (ms(NOON + 20), 3_000, 4)])
    again = anki.credit_pass(NOON + 30)
    assert again.eligible_min == 3
    assert [(r["entry_id"], r["minutes"]) for r in again.rows] == [
        ("anki-2026-10-15-m3", 1)
    ]
    detail = anki_rows()[-1]["detail"]
    assert detail["minutes"] == 1
    assert detail["ended_at"] == pytest.approx(NOON + 10)


def test_yesterdays_late_reviews_pay_yesterday(collection: Path) -> None:
    window(YESTERDAY_2350, NOON)
    make_collection(collection, [(ms(YESTERDAY_2350 + 1), 60_000, 1)], keep_wal=False)
    result = anki.credit_pass(NOON)
    assert result.eligible_min == 0
    assert [r["entry_id"] for r in result.rows] == ["anki-2026-10-14-m1"]
    assert anki_rows()[0]["day"] == "2026-10-14"


def test_a_refused_row_is_logged_with_its_error(
    collection: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    window(NOON - 60, NOON + 60)
    make_collection(collection, [(ms(NOON), 60_000, 1)], keep_wal=True)
    monkeypatch.setenv("TUTOR_KEY", str(tmp_path / "no-key"))
    with caplog.at_level(logging.WARNING):
        result = anki.credit_pass(NOON)
    assert not result.rows[0]["recorded"]
    assert "signing key unreadable" in caplog.text


def test_credit_now_logs_a_missing_collection(
    collection: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        assert anki.credit_now() is None
    assert "anki credit skipped" in caplog.text
    make_collection(collection, [], keep_wal=False)
    result = anki.credit_now(NOON)
    assert result is not None
    assert result.eligible_min == 0


def test_status_without_a_collection(collection: Path) -> None:
    assert not collection.exists()
    assert anki.status(NOON) == {
        "credited_today_min": 0,
        "eligible_today_min": 0,
        "last_sync_at": None,
        "unavailable": None,
    }


def test_status_credits_then_reports(collection: Path) -> None:
    window(NOON - 600, NOON + 600)
    make_collection(collection, [(ms(NOON - 1), 130_000, 1)], keep_wal=True)
    got = anki.status(NOON)
    assert got["credited_today_min"] == got["eligible_today_min"] == 2
    assert got["unavailable"] == {"until": int(NOON + 600), "reason": "rate_limit"}
    assert isinstance(got["last_sync_at"], float)
    assert credit.session_minutes(anki.session_for("2026-10-15")) == {1, 2}


def test_status_of_an_unreadable_collection_raises(collection: Path) -> None:
    collection.parent.mkdir(parents=True)
    collection.write_bytes(b"garbage")
    with pytest.raises(AnkiError):
        anki.status(NOON)
