# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Builders for the evening-gate tests: signed credit rows in a tmp ledger."""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import TYPE_CHECKING

import earned_time

from tutor.ledger_io import Paths, default_paths

if TYPE_CHECKING:
    from pathlib import Path

# Tue 2026-11-17: quota 15 minutes. Fri 2026-11-20: 30. Sat 2026-11-21: 50.
TUESDAY = date(2026, 11, 17)
FRIDAY = date(2026, 11, 20)
SATURDAY = date(2026, 11, 21)
KEY = b"tutor-test-key-not-the-real-one"


def paths() -> Paths:
    """The sandbox paths ``conftest.tutor_sandbox`` exported."""
    return default_paths()


def row(day: date, minutes: int, number: int) -> dict[str, object]:
    """One signed credit row paying ``minutes`` that ended at noon on ``day``."""
    ended = datetime(day.year, day.month, day.day, 12, 0).astimezone().timestamp()
    entry: dict[str, object] = {
        "kind": "credit",
        "entry_id": f"s-m{number}",
        "day": day.isoformat(),
        "detail": {"minutes": minutes, "ended_at": ended},
    }
    entry["hmac"] = earned_time.entry_signature(entry, KEY)
    return entry


def put(ledger: Path, rows: list[dict[str, object]]) -> None:
    """Replace the ledger file with ``rows``."""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"entries": rows}), encoding="utf-8")
