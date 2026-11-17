# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The evening lock's open-tutor flow: study mode, the strip, the way back."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import gate_open, gate_view
from tutor.tests import _gate_lock_support as support
from tutor.tests import _gate_support as sup

if TYPE_CHECKING:
    from types import SimpleNamespace

    import pytest

rig = support.rig
_Window = support.Window
_buttons = support.buttons
_lock = support.make_lock
_recorder = support.recorder
_session = support.session
PART = support.PART


def test_open_tutor_stands_the_lock_down_then_opens_the_page(
    rig: SimpleNamespace,
) -> None:
    opened: list[str] = []
    lock = _lock(opener=_recorder(opened))
    _buttons(lock).open_button.invoke()
    assert _session(lock).log == ["suspend"]
    assert opened == ["http://127.0.0.1:8778/app/"]
    assert lock.strip is not None


def test_a_failed_launch_puts_the_lock_straight_back(rig: SimpleNamespace) -> None:
    lock = _lock(opener=lambda _u: gate_open.LaunchResult(ok=False, reason="x"))
    _buttons(lock).open_button.invoke()
    assert _session(lock).log == ["suspend", "resume"]
    assert lock.strip is None


def test_no_browser_means_no_suspend(
    rig: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate_open, "find_opener", lambda: None)
    lock = _lock()
    _buttons(lock).open_button.invoke()
    assert _session(lock).log == []


def test_a_refused_suspend_opens_nothing(rig: SimpleNamespace) -> None:
    opened: list[str] = []
    lock = _lock(opener=_recorder(opened))
    _session(lock).suspend_ok = False
    _buttons(lock).open_button.invoke()
    assert not opened


def test_a_second_open_while_studying_only_opens_the_page(
    rig: SimpleNamespace,
) -> None:
    opened: list[str] = []
    lock = _lock(opener=_recorder(opened))
    panel = _buttons(lock)
    panel.open_button.invoke()
    panel.open_button.invoke()
    assert _session(lock).log == ["suspend"]
    assert len(opened) == 2


def test_back_to_lock_resumes_and_drops_the_strip(rig: SimpleNamespace) -> None:
    lock = _lock()
    _buttons(lock).open_button.invoke()
    assert lock.strip is not None
    lock.strip.back_button.invoke()
    assert _session(lock).log == ["suspend", "resume"]
    assert lock.strip is None


def test_end_evening_from_the_strip_exits_ten(rig: SimpleNamespace) -> None:
    lock = _lock()
    _buttons(lock).open_button.invoke()
    assert lock.strip is not None
    lock.strip.end_button.invoke()
    assert lock.exit_code == 10
    assert lock.strip is None


def test_a_credit_during_study_closes_and_drops_the_strip(
    rig: SimpleNamespace,
) -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 15, 15)])
    lock = _lock()
    _buttons(lock).open_button.invoke()
    rig.watch["on_credit"]()
    assert lock.strip is None
    assert lock.exit_code == 0


def test_a_progress_tick_updates_the_strip_too(rig: SimpleNamespace) -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 6, 6)])
    lock = _lock()
    _buttons(lock).open_button.invoke()
    assert lock.strip is not None
    rig.watch["is_done"]()
    assert len(lock.strip.quota_bar.find_withtag("done")) == 6


def test_no_output_means_no_strip_but_study_still_runs(rig: SimpleNamespace) -> None:
    lock = _lock()
    _Window.instances[0].outputs = ()
    _buttons(lock).open_button.invoke()
    assert lock.strip is None
    assert _session(lock).log == ["suspend"]


def test_an_opener_that_raises_is_a_failed_launch(rig: SimpleNamespace) -> None:
    def boom(_url: str) -> gate_open.LaunchResult:
        raise OSError

    lock = _lock(opener=boom)
    _buttons(lock).open_button.invoke()
    assert _session(lock).log == ["suspend", "resume"]
    assert _buttons(lock).warn.cget("text") == gate_view.WARN


def test_a_refused_suspend_flags_the_surface(rig: SimpleNamespace) -> None:
    lock = _lock()
    _session(lock).suspend_ok = False
    _buttons(lock).open_button.invoke()
    assert _buttons(lock).warn.cget("text") == gate_view.WARN
