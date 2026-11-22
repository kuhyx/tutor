# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C1: a teaching turn's credit row names its subject and module, signed.

leetcode-guard pays theory minutes on the modules of its current unit from
these keys (``DOCS-contract.md`` §7). Every other row (drill, app review,
Anki, leftover, carry) stays as it was: no ``subject``, no ``module``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

import earned_time
from gatelock import log_integrity

from tutor import credit, unit_credit
from tutor.cards import Card, Topic
from tutor.engine import Engine
from tutor.ledger_io import default_paths
from tutor.store import Store
from tutor.tests._credit_support import NOON, put, unit
from tutor.tests._cur import T0, card, make_ctx, module, subject
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path

CARD = Card("io-x", "Q?", "A.", "https://e.org/x", "ex", Topic("io", "I/O", ("io",)))


def _ledger() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(default_paths().ledger.read_text())[
        "entries"
    ]
    return rows


def _teach(root: Path) -> Engine:
    """Subject ``car``, module ``a``: three 170 s answers on the untaught ``c0``."""
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(2)}
    subject(ctx, modules=[module("a", status="ready", cards=2)], found=found)
    clock = ManualClock(T0 / 1000)
    fake = FakeSession(*[turn() for _ in range(4)])
    engine = Engine(store=Store(root), now=clock, session_factory=lambda _p: fake)
    asyncio.run(engine.start("c0", subject="car"))
    for i in range(3):
        clock.advance(170)
        asyncio.run(engine.reply("the answer, at length", msg_id=f"m{i}"))
    return engine


def _units(rows: list[dict[str, Any]], day: str) -> int | None:
    """What earned_time's tutor earner pays for ``day`` on exactly ``rows``."""
    where = default_paths()
    put(where, list(rows))
    day_ = datetime.fromisoformat(day).date()
    got: int | None = earned_time.credit_units(
        earned_time.TUTOR, where.ledger, where.key_file, day_
    )
    return got


def _without_c1(row: dict[str, Any]) -> dict[str, Any]:
    """``row`` as the writer signed it before C1: no subject / module."""
    detail = {k: v for k, v in row["detail"].items() if k not in {"subject", "module"}}
    body = {k: v for k, v in row.items() if k != "hmac"} | {"detail": detail}
    return body | {"hmac": earned_time.entry_signature(body, KEY)}


def test_a_teaching_turn_row_carries_signed_subject_and_module(tmp_path: Path) -> None:
    engine = _teach(tmp_path)
    rows = _ledger()
    assert rows
    assert {(r["detail"]["subject"], r["detail"]["module"]) for r in rows} == {
        ("car", "a")
    }
    assert all(earned_time.verified(r, KEY) for r in rows)
    assert engine.receipts[-1]["recorded"] is True


def test_the_earner_pays_the_same_with_or_without_the_c1_keys(tmp_path: Path) -> None:
    _teach(tmp_path)
    rows = _ledger()
    day = rows[0]["day"]
    with_keys = _units(rows, day)
    assert with_keys
    assert _units([_without_c1(r) for r in rows], day) == with_keys
    assert _units([*map(_without_c1, rows[:-1]), rows[-1]], day) == with_keys


def test_gatelock_signs_a_c1_row_the_same_way(tmp_path: Path) -> None:
    _teach(tmp_path)
    row = _ledger()[-1]
    body = {k: v for k, v in row.items() if k != "hmac"}
    got = log_integrity.compute_entry_hmac(body, key_file=default_paths().key_file)
    assert got == row["hmac"]


def test_rows_without_a_taught_card_get_no_c1_keys() -> None:
    rows = unit_credit.credit_units(
        [unit(1), unit(2)], "drill-1", now=NOON, subject="car"
    )
    assert rows[0]["recorded"] is True
    assert not {"subject", "module"} & set(_ledger()[0]["detail"])
    unit_credit.teaching_units([unit(1)], "early", now=NOON, subject="x", card=None)
    assert not {"subject", "module"} & set(_ledger()[-1]["detail"])


def test_a_trimmed_teaching_row_stays_signed_with_its_module() -> None:
    assert credit.credit_span(unit(150), 150, "morning", now=NOON).minutes == 150
    longer = [unit(n) for n in range(1, 31)]
    rows = unit_credit.teaching_units(
        longer, "evening", now=NOON, subject="automation", card=CARD
    )
    assert rows[0]["minutes"] == 10  # the 160-min daily cap trimmed it
    row = _ledger()[-1]
    assert (row["detail"]["subject"], row["detail"]["module"]) == ("automation", "io")
    assert row["detail"]["minutes"] == 10
    assert earned_time.verified(row, KEY)
