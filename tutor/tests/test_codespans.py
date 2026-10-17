# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Markdown code: the parts of a model turn that text repairs leave alone."""

from __future__ import annotations

import pytest

from tutor import codespans


@pytest.mark.parametrize(
    ("text", "pieces"),
    [
        ("plain", [("plain", False)]),
        ("", []),
        ("a `x ? y` b", [("a ", False), ("`x ? y`", True), (" b", False)]),
        ("`x`", [("`x`", True)]),
        (
            "fence:\n```\nA?\n```\nafter",
            [("fence:\n", False), ("```\nA?\n```", True), ("\nafter", False)],
        ),
        ("open ```\nnever closed", [("open ", False), ("```\nnever closed", True)]),
        ("one ` tick", [("one ` tick", False)]),
    ],
    ids=["plain", "empty", "inline", "only-code", "fence", "open-fence", "lone-tick"],
)
def test_pieces_mark_code(text: str, pieces: list[tuple[str, bool]]) -> None:
    assert codespans.pieces(text) == pieces
    assert "".join(chunk for chunk, _ in pieces) == text
