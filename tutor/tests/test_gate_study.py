# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Study mode: release the grab so the browser gets keys, take it back after."""

from __future__ import annotations

import tkinter as tk
from typing import Literal
from unittest.mock import MagicMock

import gatelock
import pytest

from tutor import gate_study


def _config(
    *, grab: Literal["global", "local"] = "global", vt: bool = True
) -> gatelock.LockConfig:
    return gatelock.LockConfig(
        mode="hard",
        overrideredirect=True,
        grab=gatelock.GrabPolicy(kind=grab, disable_vt=vt),
    )


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """One parent mock recording every call in order, lock and gatelock alike."""
    parent = MagicMock()
    monkeypatch.setattr(gatelock, "restore_vt_switching", parent.vt_restore)
    monkeypatch.setattr(gatelock, "disable_vt_switching", parent.vt_disable)
    return parent


def _session(
    calls: MagicMock, config: gatelock.LockConfig | None = None
) -> gate_study.StudySession:
    lock = calls.lock
    return gate_study.StudySession(lock, config or _config(), on_fail=calls.fail)


def _names(calls: MagicMock) -> list[str]:
    return [c[0] for c in calls.mock_calls]


def test_suspend_stops_the_loops_before_it_releases_the_grab(calls: MagicMock) -> None:
    session = _session(calls)
    assert session.suspend()
    assert session.active
    order = _names(calls)
    expected = [
        "lock.recovery.stop",
        "lock.detector.stop",
        "lock.report_grab_held",
        "lock.root.grab_release",
        "vt_restore",
        "lock.surfaces.set_visible",
        "lock.root.withdraw",
    ]
    assert order == expected
    calls.lock.report_grab_held.assert_called_once_with(held=False)
    calls.lock.surfaces.set_visible.assert_called_once_with(visible=False)


def test_suspend_leaves_vt_alone_when_the_lock_never_disabled_it(
    calls: MagicMock,
) -> None:
    session = _session(calls, _config(grab="local", vt=False))
    assert session.suspend()
    assert "vt_restore" not in _names(calls)


def test_suspend_twice_is_a_no_op(calls: MagicMock) -> None:
    session = _session(calls)
    session.suspend()
    calls.reset_mock()
    assert session.suspend()
    assert not calls.mock_calls


def test_a_grab_that_will_not_release_rolls_back(calls: MagicMock) -> None:
    calls.lock.root.grab_release.side_effect = tk.TclError("no")
    session = _session(calls)
    assert not session.suspend()
    assert not session.active
    calls.lock.report_grab_held.assert_called_with(held=True)
    calls.lock.recovery.start.assert_called_once()
    calls.lock.detector.start.assert_called_once()
    calls.lock.surfaces.set_visible.assert_not_called()


def test_an_unexpected_failure_puts_the_whole_lock_back(calls: MagicMock) -> None:
    calls.lock.surfaces.set_visible.side_effect = [RuntimeError("wedged"), None]
    session = _session(calls)
    assert not session.suspend()
    assert not session.active
    calls.vt_disable.assert_called_once()
    calls.lock.root.grab_set_global.assert_called()
    calls.lock.recovery.start.assert_called_once()
    assert calls.lock.surfaces.set_visible.call_args_list[-1].kwargs == {
        "visible": True
    }


def test_resume_strengthens_before_it_grabs(calls: MagicMock) -> None:
    session = _session(calls)
    session.suspend()
    calls.reset_mock()
    assert session.resume()
    assert not session.active
    order = _names(calls)
    assert order == [
        "lock.root.deiconify",
        "lock.root.update_idletasks",
        "vt_disable",
        "lock.surfaces.set_visible",
        "lock.root.focus_force",
        "lock.root.grab_set_global",
        "lock.report_grab_held",
        "lock.detector.start",
        "lock.recovery.start",
    ]
    calls.lock.report_grab_held.assert_called_once_with(held=True)


def test_resume_when_not_studying_does_nothing(calls: MagicMock) -> None:
    session = _session(calls)
    assert session.resume()
    assert not calls.mock_calls


def test_a_grab_that_cannot_be_retaken_degrades_but_restarts_recovery(
    calls: MagicMock,
) -> None:
    session = _session(calls)
    session.suspend()
    calls.lock.root.grab_set_global.side_effect = tk.TclError("held by a browser")
    calls.reset_mock()
    assert not session.resume()
    assert calls.lock.root.grab_set_global.call_count == gate_study.REGRAB_ATTEMPTS
    calls.fail.assert_called_once()
    calls.lock.recovery.start.assert_called_once()


def test_a_local_grab_lock_regrabs_locally(calls: MagicMock) -> None:
    session = _session(calls, _config(grab="local", vt=False))
    session.suspend()
    session.resume()
    calls.lock.root.grab_set.assert_called_once()
    calls.lock.root.grab_set_global.assert_not_called()
    assert "vt_disable" not in _names(calls)


def test_a_failing_restart_of_a_loop_is_logged_not_raised(
    calls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    session = _session(calls)
    session.suspend()
    calls.lock.detector.start.side_effect = tk.TclError("gone")
    assert session.resume()
    calls.lock.recovery.start.assert_called_once()
    assert "detector" in caplog.text


def test_a_loop_that_will_not_stop_refuses_study(calls: MagicMock) -> None:
    calls.lock.recovery.stop.side_effect = tk.TclError("stuck")
    session = _session(calls)
    assert not session.suspend()
    calls.lock.root.grab_release.assert_not_called()


def test_one_failing_restore_step_does_not_skip_the_rest(calls: MagicMock) -> None:
    session = _session(calls)
    session.suspend()
    calls.lock.root.deiconify.side_effect = RuntimeError("x")
    assert session.resume()
    calls.lock.surfaces.set_visible.assert_called_with(visible=True)
    calls.lock.root.grab_set_global.assert_called_once()
