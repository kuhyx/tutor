# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C2: one signed ``module_state`` row per done / not-done flip of a module.

leetcode-guard reads ``module_state.json`` to know which unit's theory is
done (``DOCS-contract-module-state.md``). Every path that can flip a module
writes the row: a card taught, a card un-taught, cards added by generation,
cards suspended by regeneration, and the startup backfill.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import earned_time
from gatelock import log_integrity

from tutor.curriculum import cardgen, judge, module_state, regen, wiki
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.source import SubjectSource
from tutor.engine import Engine
from tutor.ledger_io import default_paths
from tutor.store import Store
from tutor.tests._cur import T0, card, make_ctx, module, subject
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

LC = "leetcode-easy-algorithms-in-typescript"
JS = "javascript-and-pandas-for-leetcode-easy"
SQL = "mysql-8-for-timed-sql-coding-tests-joins-and"


def _rows(root: Path) -> list[dict[str, Any]]:
    path = root / "module_state.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    assert raw["version"] == 1
    rows: list[dict[str, Any]] = raw["entries"]
    return rows


def _flips(root: Path) -> list[tuple[str, str, bool]]:
    return [
        (r["detail"]["subject"], r["detail"]["module"], r["detail"]["done"])
        for r in _rows(root)
    ]


def _lc(tmp_path: Path, **found: Any) -> tuple[Context, Fakes, SubjectSource]:
    ctx, fakes = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    subject(ctx, LC, modules=mods, found=found)
    return ctx, fakes, SubjectSource(Store(tmp_path), ctx, LC)


def _taught(ctx: Context, cid: str, subj: str = LC) -> None:
    ctx.log.append([worker_event("taught", (subj, cid), dev=ctx.device, at=T0)])


def test_teaching_the_last_live_card_writes_a_signed_done_row(tmp_path: Path) -> None:
    ctx, fakes, src = _lc(tmp_path, a0=card("a", 0), a1=card("a", 1))
    src.mark("a0", "s1", done=True)
    assert _rows(tmp_path) == []  # a1 is still untaught: no flip
    fakes.now[0] = T0 + 5_000
    src.mark("a1", "s1", done=True)
    (row,) = _rows(tmp_path)
    assert row == {
        "kind": "module_state",
        "entry_id": f"state:{LC}:a:1",
        "day": "2027-01-15",
        "detail": {"subject": LC, "module": "a", "done": True, "at": T0 / 1000 + 5},
        "hmac": row["hmac"],
    }
    assert earned_time.verified(row, KEY)
    assert ctx.fold().card(LC, "a1").taught


def test_untaught_flips_the_module_back(tmp_path: Path) -> None:
    _, _, src = _lc(tmp_path, a0=card("a", 0))
    src.mark("a0", "s1", done=True)
    src.mark("a0", "s1", done=False)
    src.mark("a0", "s1", done=False)  # no flip: nothing written
    assert _flips(tmp_path) == [(LC, "a", True), (LC, "a", False)]
    assert [r["entry_id"] for r in _rows(tmp_path)] == [
        f"state:{LC}:a:1",
        f"state:{LC}:a:2",
    ]


def test_generation_adding_a_card_to_a_done_module_flips_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = make_ctx(tmp_path)
    source = wiki.Source("https://en.wikipedia.org/wiki/A", "A", "text a")
    monkeypatch.setattr(cardgen, "sources", lambda *_: [source])
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    found = {"a0": card("a", 0)}
    subject(ctx, LC, modules=[module("a", status="generating")], found=found)
    _taught(ctx, "a0")
    drafted = {
        "id": "a-new",
        "front": "What does part 1 do?",
        "back": "It turns.",
        "source": 1,
        "excerpt": "part 1 turns the crank shaft round and round",
        "requires": [],
    }
    fakes.replies.append({"cards": [drafted]})
    assert cardgen.generate(ctx, LC, "a")["status"] == "ready"
    assert _flips(tmp_path) == [(LC, "a", True), (LC, "a", False)]


def test_regeneration_suspending_the_untaught_card_flips_done(tmp_path: Path) -> None:
    ctx, fakes, _ = _lc(tmp_path, good=card("a", 1), toy=card("a", 2))
    _taught(ctx, "good")
    assert _rows(tmp_path) == []
    verdicts = [
        {"id": i, "on_topic": i == "good", "module": "a", "reason": "r"}
        for i in ("good", "toy")
    ]
    fakes.replies.append({"verdicts": verdicts})
    assert regen.regenerate(ctx, LC, "a")["suspended"] == ["toy"]
    assert _flips(tmp_path) == [(LC, "a", True)]


def test_other_subjects_write_no_rows(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(
        ctx, "car", modules=[module("a", status="ready")], found={"c": card("a", 0)}
    )
    _taught(ctx, "c", "car")
    assert not (tmp_path / "module_state.json").exists()


def test_startup_backfills_every_module_once(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    subject(ctx, LC, modules=mods, found={"a0": card("a", 0)})
    subject(ctx, JS, modules=[module("js", status="ready")])
    subject(ctx, SQL, modules=[module("joins", status="ready")])
    subject(ctx, "car", modules=[module("x", status="ready")])
    _taught(ctx, "a0")
    engine = Engine(store=Store(tmp_path))
    engine.record_module_states()
    want = [(LC, "a", True), (LC, "b", False), (JS, "js", False), (SQL, "joins", False)]
    assert sorted(_flips(tmp_path)) == sorted(want)
    engine.record_module_states()  # a second start: the truth is on file already
    assert sorted(_flips(tmp_path)) == sorted(want)


def test_an_unverified_row_is_not_the_latest(tmp_path: Path) -> None:
    ctx, _, src = _lc(tmp_path, a0=card("a", 0))
    path = tmp_path / "module_state.json"
    detail = {"subject": LC, "module": "a", "done": True, "at": 1.0}
    forged: dict[str, Any] = {"kind": "module_state", "entry_id": f"state:{LC}:a:1"}
    forged |= {"day": "2027-01-15", "detail": detail, "hmac": "x"}
    path.write_text(json.dumps({"version": 1, "entries": [forged, "junk"]}))
    src.mark("a0", "s1", done=True)  # truth done; the only done row is forged
    rows = _rows(tmp_path)
    assert [r["entry_id"] for r in rows[2:]] == [f"state:{LC}:a:2"]
    assert rows[2]["detail"]["done"] is True
    assert earned_time.verified(rows[2], KEY)
    assert ctx.fold().card(LC, "a0").taught


def test_gatelock_verifies_a_c2_row(tmp_path: Path) -> None:
    _, _, src = _lc(tmp_path, a0=card("a", 0))
    src.mark("a0", "s1", done=True)
    (row,) = _rows(tmp_path)
    key_file = default_paths().key_file
    assert log_integrity.verify_entry_hmac(row, key_file=key_file)
    body = {k: v for k, v in row.items() if k != "hmac"}
    assert log_integrity.compute_entry_hmac(body, key_file=key_file) == row["hmac"]


def test_a_write_failure_logs_and_never_breaks_teaching(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, _, src = _lc(tmp_path, a0=card("a", 0))
    (tmp_path / "module_state.json").mkdir()
    with caplog.at_level(logging.WARNING):
        src.mark("a0", "s1", done=True)
    assert ctx.fold().card(LC, "a0").taught
    assert "module state" in caplog.text


def test_an_unreadable_key_logs_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, _, src = _lc(tmp_path, a0=card("a", 0))
    monkeypatch.setenv("TUTOR_KEY", str(tmp_path / "missing.key"))
    with caplog.at_level(logging.WARNING):
        src.mark("a0", "s1", done=True)
    assert ctx.fold().card(LC, "a0").taught
    assert not (tmp_path / "module_state.json").exists()
    assert "module state" in caplog.text


def test_the_subjects_are_the_two_gated_ones_and_sql() -> None:
    assert frozenset({LC, JS, SQL}) == module_state.SUBJECTS
