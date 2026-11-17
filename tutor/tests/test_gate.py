# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor.gate --production --evening``: decide, wait, lock, exit code."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ClassVar

import gatelock
import pytest

from tutor import gate, gate_state
from tutor.tests import _gate_support as sup

if TYPE_CHECKING:
    from collections.abc import Callable


class _Lock:
    """Stands in for ``EveningLock``: records its arguments, 'runs' to a code."""

    built: ClassVar[list[_Lock]] = []
    code = 0

    def __init__(
        self, paths: Any, progress: Any, *, today: Any, production: bool
    ) -> None:
        self.progress = progress
        self.production = production
        self.today = today
        self.exit_code = type(self).code
        self.ran = False
        type(self).built.append(self)

    def run(self) -> None:
        self.ran = True


@pytest.fixture(autouse=True)
def _fresh_lock() -> None:
    _Lock.built = []
    _Lock.code = 0


def _run(
    *,
    wait_x: Callable[..., bool] = lambda **_: True,
    production: bool = True,
) -> int:
    return gate.run_evening(
        sup.paths(),
        production=production,
        today=sup.TUESDAY,
        wait_x=wait_x,
        lock_factory=_Lock,
    )


def _no_x_wait(**_: Any) -> bool:
    msg = "a paid day must not wait for X"
    raise AssertionError(msg)


def test_paid_exits_zero_with_no_window_and_no_x_wait() -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 15, 15)])
    assert _run(wait_x=_no_x_wait) == 0
    assert not _Lock.built


def test_no_x_within_the_bound_exits_three_without_a_window() -> None:
    seen: dict[str, Any] = {}

    def wait(**kwargs: Any) -> bool:
        seen.update(kwargs)
        return False

    assert _run(wait_x=wait) == 3
    assert seen["timeout_s"] == 10.0
    assert not _Lock.built


def test_unpaid_locks_with_todays_progress_and_returns_its_exit_code() -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 7, 7)])
    _Lock.code = 10
    assert _run() == 10
    (lock,) = _Lock.built
    assert lock.ran
    assert lock.production is True
    assert lock.progress == gate_state.Progress(minutes=7, quota=15, paid=False)


def test_a_credit_that_closes_the_window_exits_zero() -> None:
    assert _run() == 0
    assert _Lock.built[0].ran


def test_could_not_check_still_locks() -> None:
    sup.paths().key_file.unlink()
    assert _run() == 0
    (lock,) = _Lock.built
    assert lock.progress is None


def test_without_evening_it_prints_usage_and_exits_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert gate.main(["--production"]) == 2
    assert "--evening" in capsys.readouterr().err


def test_main_passes_production_through(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake(paths: Any, **kwargs: Any) -> int:
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(gate, "run_evening", fake)
    assert gate.main(["--production", "--evening"]) == 0
    assert gate.main(["--evening"]) == 0
    assert [c["production"] for c in calls] == [True, False]


def test_end_evening_code_comes_from_the_chain_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert gate.end_evening_code() == 10
    chain = SimpleNamespace(EXIT_END_EVENING=42)
    monkeypatch.setitem(__import__("sys").modules, "gatelock.evening_chain", chain)
    monkeypatch.setattr(gatelock, "evening_chain", chain, raising=False)
    assert gate.end_evening_code() == 42
