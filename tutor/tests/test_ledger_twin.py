# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The twin writer and the card lookup fail soft: never a raise, never a bad row."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tutor import ledger_twin, review_tag
from tutor.ledger_io import Paths
from tutor.ledger_pay import Taught
from tutor.tests._relay_support import engine

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ALWAYS = Taught(subject="car", module="a", activity="review")


def _ask(_entry: str, _ended: float) -> Taught:
    return ALWAYS


def test_no_key_means_no_twin(tmp_path: Path) -> None:
    where = Paths(data_dir=tmp_path, key_file=tmp_path / "missing.key")
    assert ledger_twin.backfill(_ask, paths=where) == []
    assert not where.ledger.exists()


def test_an_unreadable_ledger_is_logged_and_left_alone(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "key").write_bytes(b"k")
    where = Paths(data_dir=tmp_path, key_file=tmp_path / "key")
    where.ledger.write_text("{not json", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="tutor.ledger_twin"):
        assert ledger_twin.backfill(_ask, paths=where) == []
    assert "not re-signed" in caplog.text
    assert where.ledger.read_text(encoding="utf-8") == "{not json"


def test_a_bad_subject_or_cards_file_resolves_to_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = engine(tmp_path)[0].ctx
    resolve = review_tag.card_modules(ctx)
    with caplog.at_level(logging.WARNING, logger="tutor.review_tag"):
        assert resolve("../escape", "a-1") is None
        (tmp_path / "data/subjects/car").mkdir(parents=True)
        (tmp_path / "data/subjects/car/cards.json").write_text("{", encoding="utf-8")
        assert resolve("car", "a-1") is None
    assert caplog.text.count("unreadable") == 2
    assert review_tag.taught_by({"s": 7, "c": "a-1"}, resolve) is None
    assert review_tag.taught_by({"s": "car", "c": "a-1"}, None) is None
