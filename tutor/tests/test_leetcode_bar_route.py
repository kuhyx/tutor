# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The guard route's URL, its state log and the seam that keeps tests off the live one."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from tutor import guard_route, leetcode_bar
from tutor.tests._cur import T0, card, make_ctx, module, subject
from tutor.tests._guard_theory import URL, GuardFake, theory
from tutor.tests._phase import LC, grant

if TYPE_CHECKING:
    from pathlib import Path

_LOGGER = "tutor.guard_route"


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == _LOGGER and r.levelno >= logging.WARNING
    ]


def _ask(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, LC, modules=[module("a", status="ready")], found={"a0": card("a", 0)})
    leetcode_bar.session_map(ctx, LC, "a0", T0 / 1000)


def test_the_route_state_is_logged_when_it_changes_only(
    tmp_path: Path,
    guard_theory: GuardFake,
    caplog: pytest.LogCaptureFixture,
    clock: _Clock,
) -> None:
    grant((LC, "a"))
    with caplog.at_level(logging.INFO):
        # Still down on an answer without a map: no second line.
        for reply in (
            OSError("x"),
            OSError("y"),
            b'{"theory": 1}',
            theory(),
            theory(),
            500,
            500,
        ):
            guard_theory.reply = reply
            clock.now += guard_route.RETRY_S  # each ask is past the window
            _ask(tmp_path)
    assert len(_warnings(caplog)) == 3  # down, back, down again


def test_a_check_that_found_nothing_is_not_an_outage(
    tmp_path: Path, guard_theory: GuardFake, caplog: pytest.LogCaptureFixture
) -> None:
    grant((LC, "a"))
    guard_theory.reply = theory(checked=False)
    with caplog.at_level(logging.INFO):
        _ask(tmp_path)
    assert _warnings(caplog) == []


def test_the_url_resolves_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    assert guard_route.theory_url() == URL  # conftest's fake
    monkeypatch.delenv("TUTOR_GUARD_THEORY_URL")
    assert guard_route.theory_url() == "http://127.0.0.1:8771/api/theory"
    monkeypatch.setenv("TUTOR_GUARD_THEORY_URL", "http://x.invalid/t")
    assert guard_route.theory_url() == "http://x.invalid/t"


def test_no_test_can_reach_the_live_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the env seam the default is the live URL, which the fake refuses."""
    monkeypatch.delenv("TUTOR_GUARD_THEORY_URL")
    with pytest.raises(AssertionError, match="live guard"):
        guard_route.fetch()


@pytest.mark.parametrize("url", ["file:///etc/hostname", "https://x.invalid/t", "x"])
def test_only_an_http_url_is_ever_opened(
    monkeypatch: pytest.MonkeyPatch, guard_theory: GuardFake, url: str
) -> None:
    monkeypatch.setenv("TUTOR_GUARD_THEORY_URL", url)
    assert guard_route.fetch() is None
    assert guard_theory.timeouts == []


class _Clock:
    """A settable stand-in for ``guard_route.clock``."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(guard_route, "clock", fake)
    return fake


def test_a_failed_fetch_is_not_repeated_for_30_s(
    tmp_path: Path, guard_theory: GuardFake, clock: _Clock
) -> None:
    grant((LC, "a"))
    guard_theory.reply = TimeoutError("accepts, never answers")
    _ask(tmp_path)
    clock.now += guard_route.RETRY_S - 1
    _ask(tmp_path)
    assert len(guard_theory.timeouts) == 1  # the second publish did not wait
    clock.now += 1
    _ask(tmp_path)
    assert len(guard_theory.timeouts) == 2  # the window is over: ask again


def test_a_success_clears_the_window(
    tmp_path: Path, guard_theory: GuardFake, clock: _Clock
) -> None:
    grant((LC, "a"))
    guard_theory.reply = OSError("down")
    _ask(tmp_path)
    clock.now += guard_route.RETRY_S
    guard_theory.reply = theory()
    _ask(tmp_path)
    _ask(tmp_path)  # the guard is back: no retry window, a 5 s cache
    assert len(guard_theory.timeouts) == 2
    clock.now += guard_route.CACHE_S
    _ask(tmp_path)
    assert len(guard_theory.timeouts) == 3


def test_an_answer_without_a_map_does_not_open_the_window(
    tmp_path: Path, guard_theory: GuardFake, clock: _Clock
) -> None:
    grant((LC, "a"))
    guard_theory.reply = b'{"theory": 1}'
    _ask(tmp_path)
    _ask(tmp_path)
    assert len(guard_theory.timeouts) == 2
