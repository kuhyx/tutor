# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Credited minutes per day, for the curriculum ``stats`` node.

They come from the ledger's verified credit rows, the same rows the earner
pays, capped per local day like it.
"""

from __future__ import annotations

from collections import Counter
import logging
from typing import TYPE_CHECKING

from tutor.credit import local_day
from tutor.ledger_io import LedgerError, default_paths, read_key, read_rows
from tutor.ledger_pay import DAILY_CAP_MINUTES, paying

if TYPE_CHECKING:
    from tutor.ledger_io import Paths

_logger = logging.getLogger(__name__)


def ledger_minutes_by_day(paths: Paths | None = None) -> dict[str, int]:
    """Local day -> verified credited minutes (capped); empty if unreadable."""
    where = paths or default_paths()
    key = read_key(where.key_file)
    if key is None:
        return {}
    try:
        rows = read_rows(where.ledger)
    except LedgerError as exc:
        _logger.warning("ledger unreadable, no minutes per day: %s", exc)
        return {}
    per_day: Counter[str] = Counter()
    for ended, minutes in paying(rows, key).values():
        per_day[local_day(ended)[0]] += minutes
    return {day: min(m, DAILY_CAP_MINUTES) for day, m in per_day.items()}
