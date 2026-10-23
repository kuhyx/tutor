# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_seed.py carry: signed rows in the SANDBOX ledger, never the real one."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from tutor import carry as carry_mod
from tutor.ledger_io import Paths, read_rows
from tutor.ledger_pay import paying

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "e2e_seed.py"
DAY = date(2026, 10, 23)


def _module() -> Any:
    """Load the script fresh (its REAL_DATA follows the moved HOME)."""
    spec = importlib.util.spec_from_file_location("e2e_seed", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sandbox(tmp_path: Path) -> Paths:
    (tmp_path / "data").mkdir()
    key = tmp_path / "test.key"
    key.write_text("c2FuZGJveC1rZXk=\n")
    return Paths(tmp_path / "data", key)


def test_carry_rows_verify_and_bank_the_extra(sandbox: Paths) -> None:
    seed = _module()
    ids = seed.carry(sandbox.data_dir, sandbox.key_file, DAY, 130)
    assert ids == [
        "20261023-090000-e2e9-m50",
        "20261023-100000-e2e0-m50",
        "20261023-110000-e2e1-m30",
    ]
    key = sandbox.key_file.read_bytes().strip()
    paid = paying(read_rows(sandbox.ledger), key)
    assert sorted(paid) == sorted(ids)
    assert sum(m for _, m in paid.values()) == 130
    # Friday's quota is 30: 100 banked (the cap); Saturday's target is 50.
    bank = carry_mod.bank_of(paid, date(2026, 10, 24))
    assert (bank.before, bank.target) == (100, 50)


def test_carry_refuses_the_real_data_dir_and_key(sandbox: Paths) -> None:
    seed = _module()
    with pytest.raises(seed.SeedError, match="real data dir"):
        seed.carry(seed.REAL_DATA, sandbox.key_file, DAY, 10)
    seed.REAL_KEY = sandbox.key_file  # stands in for /etc/workout-locker/hmac.key
    with pytest.raises(seed.SeedError, match="real key"):
        seed.carry(sandbox.data_dir, sandbox.key_file, DAY, 10)
    assert not sandbox.ledger.exists()
