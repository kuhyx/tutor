# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The optional ``mnemonic``: one line, <= 40 words, never excerpt-checked."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.test_cards import LADDER, card, write
from tutor.cards import CardError, load_topic

if TYPE_CHECKING:
    from pathlib import Path


def test_a_card_without_a_mnemonic_has_none(tmp_path: Path) -> None:
    [loaded] = load_topic(write(tmp_path / "l.json", [card()]), LADDER)
    assert loaded.mnemonic == ""


def test_a_mnemonic_loads_trimmed(tmp_path: Path) -> None:
    raw = card(mnemonic="  Seal-in: the motor holds its own Start button.  ")
    [loaded] = load_topic(write(tmp_path / "l.json", [raw]), LADDER)
    assert loaded.mnemonic == "Seal-in: the motor holds its own Start button."


def test_forty_words_pass(tmp_path: Path) -> None:
    raw = card(mnemonic="w " * 40)
    assert load_topic(write(tmp_path / "l.json", [raw]), LADDER)[0].mnemonic


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("w " * 41, "mnemonic is over 40 words"),
        ("one line\nthen another", "mnemonic must be one line"),
        ("   ", "mnemonic must be a non-empty string"),
        (7, "mnemonic must be a non-empty string"),
    ],
)
def test_bad_mnemonics(tmp_path: Path, value: object, problem: str) -> None:
    with pytest.raises(CardError, match=problem):
        load_topic(write(tmp_path / "l.json", [card(mnemonic=value)]), LADDER)
