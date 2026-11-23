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
from tutor.tests._cur import T0, card, make_ctx, module, subject, taught
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock, turn
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path

CARD = Card("io-x", "Q?", "A.", "https://e.org/x", "ex", Topic("io", "I/O", ("io",)))


def _ledger() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(default_paths().ledger.read_text())[
        "entries"
    ]
    return rows


def _teach(root: Path, **kw: Any) -> Engine:
    """Subject ``car`` (``c0`` in module ``a``, ``c1`` in ``b``): 3 answers on c0."""
    ctx, _ = make_ctx(root)
    found = {"c0": card("a", 0), "c1": card("b", 1)}
    mods = [module(m, status="ready", cards=1) for m in ("a", "b")]
    subject(ctx, modules=mods, found=found)
    clock = ManualClock(T0 / 1000)
    fake = FakeSession(*[turn() for _ in range(4)])
    engine = Engine(store=Store(root), now=clock, session_factory=lambda _p: fake, **kw)
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
    detail = _ledger()[-1]["detail"]
    assert detail["subject"] == "x"  # the subject only: it picks the row's kind
    assert "module" not in detail


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


def test_backfill_never_tags_another_session_with_the_live_card(
    tmp_path: Path,
) -> None:
    """A backfilled session is not the one on screen: its own start tags it."""
    first = _teach(tmp_path, credit_fn=FakeCredit(error="down"))
    live = Engine(
        store=Store(tmp_path),
        now=ManualClock(T0 / 1000 + 600),
        session_factory=lambda _p: FakeSession(turn()),
    )
    taught(make_ctx(tmp_path)[0], "car", "c1", T0)  # b started: no module gate
    asyncio.run(live.start("c1", subject="car"))  # module ``b`` on screen
    live.backfill_today()
    rows = _ledger()
    assert {r["detail"]["session_id"] for r in rows} == {first.session_id}
    assert {(r["detail"]["subject"], r["detail"]["module"]) for r in rows} == {
        ("car", "a")  # its own card c0, never c1 on screen
    }
    assert {r["kind"] for r in rows} == {"credit"}


def test_backfill_names_the_subject_only_when_its_card_is_gone(
    tmp_path: Path,
) -> None:
    first = _teach(tmp_path, credit_fn=FakeCredit(error="down"))
    path = tmp_path / "sessions" / f"{first.session_id}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = json.loads(lines[0]) | {"subject": "gone"}
    path.write_text("\n".join([json.dumps(start), *lines[1:]]) + "\n", "utf-8")
    Engine(store=Store(tmp_path), now=ManualClock(T0 / 1000 + 600)).backfill_today()
    rows = _ledger()
    assert rows
    assert all(r["detail"]["subject"] == "gone" for r in rows)
    assert not any("module" in r["detail"] for r in rows)


def test_a_pre_curriculum_transcript_backfills_as_the_old_deck(
    tmp_path: Path,
) -> None:
    first = _teach(tmp_path, credit_fn=FakeCredit(error="down"))
    path = tmp_path / "sessions" / f"{first.session_id}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    start = {k: v for k, v in json.loads(lines[0]).items() if k != "subject"}
    path.write_text("\n".join([json.dumps(start), *lines[1:]]) + "\n", "utf-8")
    Engine(store=Store(tmp_path), now=ManualClock(T0 / 1000 + 600)).backfill_today()
    rows = _ledger()
    assert rows
    assert {r["detail"]["subject"] for r in rows} == {"automation"}
