# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Credited minutes per day from the ledger (``progress``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import progress
from tutor.ledger_io import Paths
from tutor.tests import _credit_support as cs

if TYPE_CHECKING:
    from pathlib import Path


def paths(tmp_path: Path, key: bytes | None = cs.KEY) -> Paths:
    key_file = tmp_path / "key"
    if key is not None:
        key_file.write_bytes(key)
    return Paths(data_dir=tmp_path / "data", key_file=key_file)


def test_minutes_by_day_sums_verified_rows_capped(tmp_path: Path) -> None:
    where = paths(tmp_path)
    forged = {**cs.paid("x-m3", 5), "hmac": "0" * 64}
    rows: list[object] = [cs.paid("a-m90", 90), cs.paid("b-m80", 80), forged]
    cs.put(where, rows)
    assert progress.ledger_minutes_by_day(where) == {"2026-10-09": 160}


def test_minutes_by_day_without_key_or_ledger(tmp_path: Path) -> None:
    assert progress.ledger_minutes_by_day(paths(tmp_path, key=None)) == {}
    where = paths(tmp_path)
    where.data_dir.mkdir()
    where.ledger.write_text("not json", encoding="utf-8")
    assert progress.ledger_minutes_by_day(where) == {}
