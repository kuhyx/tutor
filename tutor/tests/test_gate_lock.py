# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The evening lock: hooks, exit codes, the credit watch, the controls."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from tutor import gate_view
from tutor.gate_state import Progress
from tutor.tests import _gate_lock_support as support
from tutor.tests import _gate_support as sup

if TYPE_CHECKING:
    from types import SimpleNamespace

    import gatelock
    import pytest

rig = support.rig
_Window = support.Window
_buttons = support.buttons
_lock = support.make_lock
_recorder = support.recorder
_session = support.session
PART = support.PART


def test_production_is_a_hard_global_grab_at_rank_150(rig: SimpleNamespace) -> None:
    lock = _lock()
    window = _Window.instances[0]
    assert window.config.resolved_grab() == "global"
    assert window.config.resolved_disable_vt() is True
    assert window.config.rank == 150
    assert rig.arbiters[0]["args"] == ("tutor_gate", 150)
    assert rig.waited == [rig.arbiter]
    rig.arbiter.publish.assert_called_once()
    rig.arbiter.acquire_holder.assert_called_once()
    assert window.grabbed
    assert lock.exit_code == 0


def test_demo_takes_a_local_grab_and_does_not_queue(rig: SimpleNamespace) -> None:
    _lock(production=False)
    config = _Window.instances[0].config
    assert config.resolved_grab() == "local"
    assert config.resolved_disable_vt() is False
    assert not rig.waited


def test_the_credit_watch_targets_the_ledger_and_polls_fast(
    rig: SimpleNamespace,
) -> None:
    _lock()
    assert rig.watch["paths"] == [sup.paths().ledger]
    assert rig.watch["poll"] <= 3000


def test_a_landed_credit_closes_with_zero(rig: SimpleNamespace) -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 15, 15)])
    lock = _lock()
    assert rig.watch["is_done"]() is True
    rig.watch["on_credit"]()
    assert _Window.instances[0].closed == 1
    assert lock.exit_code == 0


def test_a_partial_credit_repaints_and_keeps_the_lock(rig: SimpleNamespace) -> None:
    sup.put(sup.paths().ledger, [sup.row(sup.TUESDAY, 9, 9)])
    lock = _lock()
    assert rig.watch["is_done"]() is False
    assert len(_buttons(lock).quota_bar.find_withtag("done")) == 9
    assert _Window.instances[0].closed == 0


def test_could_not_check_never_lifts_the_lock(rig: SimpleNamespace) -> None:
    sup.paths().key_file.unlink()
    lock = _lock()
    assert rig.watch["is_done"]() is False
    assert _buttons(lock).warn.cget("text") == gate_view.WARN


def test_end_evening_is_clickable_at_t0_and_exits_with_the_chain_code(
    rig: SimpleNamespace,
) -> None:
    lock = _lock(progress=Progress(minutes=0, quota=15, paid=False))
    _buttons(lock).end_button.invoke()
    assert lock.exit_code == 10
    assert _Window.instances[0].closed == 1


def test_close_is_idempotent_and_run_hands_over_to_the_window(
    rig: SimpleNamespace,
) -> None:
    lock = _lock()
    lock.run()
    lock.close()
    lock.close()
    assert _Window.instances[0].ran
    assert _Window.instances[0].closed == 1


def test_a_surface_that_goes_away_is_forgotten(rig: SimpleNamespace) -> None:
    lock = _lock()
    window = _Window.instances[0]
    assert "DP-0" in lock.panels
    lock.teardown_surface(cast("gatelock.SurfaceInfo", window.surface))
    assert not lock.panels
    lock.teardown_surface(cast("gatelock.SurfaceInfo", window.surface))  # twice is fine


def test_hooks_that_need_no_work(
    rig: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    lock = _lock()
    lock.on_focus_ready(None)
    lock.on_callback_error()
    assert "callback" in caplog.text
    assert _buttons(lock).warn.cget("text") == gate_view.WARN
