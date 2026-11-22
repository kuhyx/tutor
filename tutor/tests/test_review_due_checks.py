# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C4: verifying ``review_due.json``, the reader, and the failure modes.

leetcode-guard reads it to count a module's due reviews at any time T
(``DOCS-contract-review-due.md``). Every path that moves a card's due time or
its queue membership rewrites the module's row: a taught event, a review, a
flag, a card commit (suspend, edit), an archive, and the startup backfill.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import earned_time
from gatelock import log_integrity

from tutor.curriculum import review_due
from tutor.curriculum.fold import fold
from tutor.ledger_io import default_paths
from tutor.tests._cur import T0, D, card
from tutor.tests._due import LC, make_lc, review, rows_of, teach
from tutor.tests.conftest import KEY

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_rows_verify_with_the_c2_helpers(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0")
    key_file = default_paths().key_file
    for row in rows_of(tmp_path):
        assert earned_time.verified(row, KEY)
        assert log_integrity.verify_entry_hmac(row, key_file=key_file)
        body = {k: v for k, v in row.items() if k != "hmac"}
        assert log_integrity.compute_entry_hmac(body, key_file=key_file) == row["hmac"]


def test_a_forged_row_fails_and_the_file_cannot_be_checked(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0", T0 - 30 * D)
    path = tmp_path / "review_due.json"
    raw = json.loads(path.read_text())
    row = raw["entries"][0]
    assert review_due.count_due(path, KEY, LC, "a", T0) == 1
    row["detail"]["due_ms"] = [T0 + 999 * D]  # pretend nothing is due
    path.write_text(json.dumps(raw))
    assert not earned_time.verified(row, KEY)
    assert not log_integrity.verify_entry_hmac(row, key_file=default_paths().key_file)
    assert review_due.count_due(path, KEY, LC, "a", T0) is None
    assert review_due.count_due(path, b"another key", LC, "a", T0) is None


def test_the_writer_replaces_a_forged_row_of_the_module(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0", T0 - 30 * D)
    path = tmp_path / "review_due.json"
    raw = json.loads(path.read_text())
    raw["entries"][0]["detail"]["due_ms"] = []
    path.write_text(json.dumps(raw))
    review(ctx, "a0", T0)
    assert review_due.count_due(path, KEY, LC, "a", T0) == 0
    assert review_due.count_due(path, KEY, LC, "a", T0 + 99 * D) == 1


def test_the_reader_skips_other_kinds_and_orders_by_time(tmp_path: Path) -> None:
    key = KEY

    def signed(mod: str, due: Any, at: float, kind: str = "review_due") -> Any:
        row: dict[str, Any] = {
            "kind": kind,
            "entry_id": f"due:{LC}:{mod}:{int(at)}",
            "day": "2027-01-15",
            "detail": {"subject": LC, "module": mod, "due_ms": due, "at": at},
        }
        row["hmac"] = str(earned_time.entry_signature(row, key))
        return row

    rows = [
        signed("a", [5], 2.0),
        signed("a", [1], 1.0),  # an older copy replayed after: the newer `at` wins
        signed("a", [9], 3.0, kind="other"),
        signed("b", [7, 8], 1.0),
    ]
    assert review_due.read_due(rows, key) == {(LC, "a"): [5], (LC, "b"): [7, 8]}
    # A signed row of this kind with no usable detail is skipped, not trusted.
    odd = signed("c", "soon", 1.0)
    assert review_due.read_due([odd], key) == {}
    assert review_due.read_due([signed("c", [True], 1.0)], key) == {}  # not a time
    assert review_due.read_due(["text"], key) is None  # not a signed row
    bad = {**rows[0], "hmac": "0" * 64}
    assert review_due.read_due([*rows, bad], key) is None


def test_count_due_is_none_for_a_missing_file_or_module(tmp_path: Path) -> None:
    path = tmp_path / "review_due.json"
    assert review_due.count_due(path, KEY, LC, "a", T0) is None  # never written
    path.write_text("not json")
    assert review_due.count_due(path, KEY, LC, "a", T0) is None
    path.write_text(json.dumps({"entries": "x"}))
    assert review_due.count_due(path, KEY, LC, "a", T0) is None
    path.write_text(json.dumps({"version": 1, "entries": []}))
    assert review_due.count_due(path, KEY, LC, "a", T0) is None  # no row for a


def test_a_write_failure_logs_and_the_review_still_completes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0", T0 - 30 * D)
    (tmp_path / "review_due.json").unlink()
    (tmp_path / "review_due.json").mkdir()  # a directory: the write cannot work
    with caplog.at_level(logging.WARNING):
        review(ctx, "a0", T0)
    assert any(e["k"] == "review" for e in ctx.log.read())
    assert fold(ctx.log.read()).card(LC, "a0").reviews == [(T0, 3)]
    assert "review due" in caplog.text


def test_an_unreadable_key_logs_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    before = (tmp_path / "review_due.json").read_text()
    monkeypatch.setenv("TUTOR_KEY", str(tmp_path / "missing.key"))
    with caplog.at_level(logging.WARNING):
        teach(ctx, "a0")
    assert ctx.log.read()
    assert (tmp_path / "review_due.json").read_text() == before
    assert "review due" in caplog.text
