# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What the guard may send: a number that is not a plausible count is left out.

Nothing the guard answers raises out of ``leetcode_bar.session_map``.
"""

from __future__ import annotations

import http.client
import logging
from typing import TYPE_CHECKING, Any

import pytest

from tutor import guard_route
from tutor.tests._guard_theory import GuardFake, theory
from tutor.tests._phase import LC, grant
from tutor.tests.test_leetcode_bar import LOCAL, _bar, _ctx, _warnings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("unit", [["a"], {"a": 1}, 7, True], ids=str)
def test_a_unit_that_is_not_a_name_is_another_unit(
    tmp_path: Path, guard_theory: GuardFake, unit: object
) -> None:
    grant((LC, "a"))
    guard_theory.reply = theory(unit=unit)
    assert _bar(_ctx(tmp_path)) == LOCAL


@pytest.mark.parametrize(
    ("over", "gone"),
    [
        ({"minutes_into_credit": 13}, {"into"}),  # more than a credit takes
        ({"minutes_per_credit": 0}, {"per_credit"}),  # a credit takes a minute
        ({"minutes_per_credit": 10_001}, {"per_credit"}),
        ({"minutes_into_credit": 10_001}, {"into"}),
        ({"credits_today": 10_001}, {"credits"}),
        ({"needed": 10**30}, {"needed"}),
        ({"needed": True, "credits_today": False}, {"needed", "credits"}),
        ({"minutes_into_credit": 12}, set()),  # the credit's last minute
        ({"minutes_per_credit": 10_000, "minutes_into_credit": 10_000}, set()),
    ],
    ids=[
        "into>per",
        "per=0",
        "per-huge",
        "into-huge",
        "credits-huge",
        "needed-big",
        "bools",
        "into=per",
        "at-the-cap",
    ],
)
def test_an_implausible_number_is_left_out_not_clamped(
    tmp_path: Path, guard_theory: GuardFake, over: dict[str, Any], gone: set[str]
) -> None:
    grant((LC, "a"))
    guard_theory.reply = theory(**over)
    got = _bar(_ctx(tmp_path))
    assert got is not None
    shown = {
        "into": over.get("minutes_into_credit", 7),
        "per_credit": over.get("minutes_per_credit", 12),
        "credits": over.get("credits_today", 0),
        "needed": over.get("needed", 7),
    }
    assert got == LOCAL | {k: v for k, v in shown.items() if k not in gone}


@pytest.mark.parametrize(
    "exc",
    [
        TypeError("x"),
        ValueError("x"),
        RecursionError("x"),
        OSError("x"),
        http.client.BadStatusLine("x"),
    ],
    ids=["type", "value", "recursion", "os", "status-line"],
)
def test_nothing_the_guard_sends_raises_out_of_the_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
) -> None:
    def boom() -> dict[str, Any]:
        raise exc

    grant((LC, "a"))
    monkeypatch.setattr(guard_route, "fetch", boom)
    with caplog.at_level(logging.WARNING):
        assert _bar(_ctx(tmp_path)) == LOCAL
    assert _warnings(caplog) == ["guard theory answer unreadable, bar blank"]
