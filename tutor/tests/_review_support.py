# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared builders for the app-review credit tests (events, log, cards, rows)."""

from __future__ import annotations

from datetime import datetime
import json
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from tutor import ledger_pay
from tutor.curriculum.eventlog import EventLog
from tutor.ledger_io import default_paths, read_key, read_rows

if TYPE_CHECKING:
    from pathlib import Path

ZONE = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=ZONE).timestamp()
DESK = "5f0c1a2b-3c4d-4e5f-8a9b-0c1d2e3f4a5b"


def at(day: int, hh: int, mm: int, ss: int = 0) -> int:
    """Unix ms of 2026-10-``day`` hh:mm:ss in Warsaw."""
    return int(datetime(2026, 10, day, hh, mm, ss, tzinfo=ZONE).timestamp() * 1000)


_N = iter(range(10_000))


def rev(
    dev: str,
    when: int,
    dur: int | None,
    kind: str = "review",
    card: str = "a-1",
) -> dict[str, Any]:
    """A logged event of ``dev`` on ``card`` answered at ``when`` after ``dur`` ms."""
    eid = f"01M4RBCX52MMHCK7K73E6K{next(_N):04d}"
    event: dict[str, Any] = {
        "dev": dev,
        "eid": eid,
        "k": kind,
        "s": "car",
        "c": card,
        "at": when,
        "rev": 1,
    }
    if kind == "review":
        event["r"] = 3
    if dur is not None:
        event["dur_ms"] = dur
    return event


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
    """An event log under ``tmp_path/data`` holding ``events``."""
    log = EventLog(tmp_path / "data")
    log.append(events)
    return log


def plant_cards(data: Path, subject: str, modules: dict[str, str]) -> None:
    """``subjects/<subject>/cards.json`` with card id -> module id."""
    cards = {
        cid: {
            "module": mod,
            "order": n,
            "front": "Q?",
            "back": "A.",
            "source": "s",
            "excerpt": "e",
        }
        for n, (cid, mod) in enumerate(modules.items(), 1)
    }
    folder = data / "subjects" / subject
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cards.json").write_text(json.dumps(cards), encoding="utf-8")


def ledger_entries() -> list[dict[str, Any]]:
    """Every row of the ledger as written, in order."""
    rows: list[dict[str, Any]] = json.loads(default_paths().ledger.read_text())[
        "entries"
    ]
    return rows
