# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor review-due``: heals a stale ``review_due.json`` on demand."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.__main__ import main as tutor_main
from tutor.curriculum import review_due_cli
from tutor.tests._cur import T0, D, card
from tutor.tests._due import LC, due_of, make_lc, review, rows_of, teach

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_stale_file_is_brought_back_to_the_log(tmp_path: Path) -> None:
    """A failed write left the old row, which reads the card due earlier."""
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0", T0 - 30 * D)
    stale = (tmp_path / "review_due.json").read_bytes()
    review(ctx, "a0", T0 - D)
    fresh = due_of(tmp_path)
    (tmp_path / "review_due.json").write_bytes(stale)
    assert due_of(tmp_path) != fresh
    assert review_due_cli.main([LC, "--data", str(tmp_path)]) == 0
    assert due_of(tmp_path) == fresh


def test_nothing_changed_writes_nothing(tmp_path: Path) -> None:
    ctx = make_lc(tmp_path, a0=card("a", 0))
    teach(ctx, "a0")
    before = (tmp_path / "review_due.json").read_bytes()
    assert review_due_cli.main([LC, "--data", str(tmp_path)]) == 0
    assert (tmp_path / "review_due.json").read_bytes() == before


def test_a_subject_without_a_due_file_is_left_alone(tmp_path: Path) -> None:
    make_lc(tmp_path)
    before = rows_of(tmp_path)
    assert review_due_cli.main(["car", "--data", str(tmp_path)]) == 0
    assert rows_of(tmp_path) == before


def test_an_unwritable_file_is_reported_and_exits_1(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    make_lc(tmp_path)
    (tmp_path / "review_due.json").write_text("not json")
    assert review_due_cli.main([LC, "--data", str(tmp_path)]) == 1
    assert f"review due of {LC} not recorded" in caplog.text


def test_python_m_tutor_runs_it(tmp_path: Path) -> None:
    make_lc(tmp_path)
    assert tutor_main(["review-due", LC, "--data", str(tmp_path)]) == 0
