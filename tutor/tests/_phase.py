# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C3 test support: the guard's signed ``theory_phase.json``, as the guard writes it.

Signed with ``gatelock.log_integrity`` (the guard's library), never with
``earned_time`` (the tutor's), so every test that grants a module also
proves the two libraries agree.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gatelock import log_integrity

from tutor.ledger_io import default_paths

LC = "leetcode-easy-algorithms-in-typescript"
JS = "javascript-and-pandas-for-leetcode-easy"
SQL = "mysql-8-for-timed-sql-coding-tests-joins-and"


def phase_row(
    teachable: list[tuple[str, str]],
    *,
    phase: str = "theory",
    kind: str = "theory_phase",
) -> dict[str, Any]:
    """The guard's row, signed by gatelock with the sandbox key."""
    row: dict[str, Any] = {
        "kind": kind,
        "entry_id": "phase",
        "day": "2027-01-15",
        "detail": {
            "unit": "a" if teachable else "",
            "phase": phase,
            "teachable": [list(pair) for pair in teachable],
            "at": 1_800_000_000.5,
        },
    }
    return sign(row)


def sign(row: dict[str, Any]) -> dict[str, Any]:
    """``row`` (re)signed by gatelock over everything but ``hmac``."""
    body = {k: v for k, v in row.items() if k != "hmac"}
    key_file = default_paths().key_file
    return body | {"hmac": log_integrity.compute_entry_hmac(body, key_file=key_file)}


def write_phase(row: object) -> Path:
    """Write ``row`` where the sandbox points ``TUTOR_THEORY_PHASE``."""
    path = Path(os.environ["TUTOR_THEORY_PHASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row), encoding="utf-8")
    return path


def grant(*teachable: tuple[str, str]) -> Path:
    """A THEORY phase that lets the tutor teach exactly ``teachable``."""
    return write_phase(phase_row(list(teachable)))
