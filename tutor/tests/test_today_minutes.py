# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``today_minutes``: zeros, never a crash, when the ledger cannot be read."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import today_minutes
from tutor.ledger_io import Paths, default_paths
from tutor.tests.test_carry import at, own

if TYPE_CHECKING:
    from pathlib import Path


def test_no_key_or_a_broken_ledger_reads_as_zero(tmp_path: Path) -> None:
    no_key = Paths(data_dir=tmp_path, key_file=tmp_path / "missing.key")
    assert today_minutes.today(at(24), paths=no_key) == (0, 0)
    real = default_paths()
    broken = Paths(data_dir=tmp_path, key_file=real.key_file)
    (tmp_path / "ledger.json").write_text("not a ledger", encoding="utf-8")
    assert today_minutes.today(at(24), paths=broken) == (0, 0)


def test_minutes_of_another_day_do_not_count() -> None:
    own(23, 5)
    assert today_minutes.today(at(24)).own == 0
    assert today_minutes.today(at(23)).own == 5
