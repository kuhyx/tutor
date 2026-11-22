# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``theory_phase.current``: the signed grant with its unit (the LeetCode bar's source)."""

from __future__ import annotations

from tutor.curriculum import theory_phase
from tutor.tests._phase import LC, grant, phase_row, write_phase


def test_current_names_the_unit_and_the_pairs() -> None:
    grant((LC, "a"))
    now = theory_phase.current()
    assert now is not None
    assert (now.unit, now.pairs) == ("a", frozenset({(LC, "a")}))


def test_current_is_none_when_the_row_cannot_be_trusted() -> None:
    write_phase(phase_row([(LC, "a")]) | {"hmac": "0" * 64})
    assert theory_phase.current() is None
