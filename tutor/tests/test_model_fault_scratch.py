# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A scratch run (TUTOR_DATA or ANTHROPIC_BASE_URL set) only logs its model faults."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import model_fault
from tutor.session import SessionError
from tutor.tests.conftest import FaultRig
from tutor.tests.test_model_fault import FENCE, entries

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_scratch_environment_is_not_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TUTOR_DATA", "/scratch/data")
    assert model_fault.live_process() is False
    monkeypatch.delenv("TUTOR_DATA")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:36191")
    assert model_fault.live_process() is False
    monkeypatch.delenv("ANTHROPIC_BASE_URL")
    assert model_fault.live_process() is True


def test_a_scratch_monitor_without_a_spool_never_files_or_toasts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TUTOR_DATA", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    notices: list[str] = []
    mon = model_fault.Monitor(
        notify=lambda: notices.append("toast"), live=lambda: False
    )
    mon.failed(SessionError("model error: x"))
    mon.stderr_line(FENCE)
    assert notices == []
    assert not (tmp_path / "app-errors-spool").exists()


def test_an_explicit_spool_files_even_in_a_scratch_run(tmp_path: Path) -> None:
    spool = tmp_path / "spool"
    mon = model_fault.Monitor(spool=spool, notify=lambda: None, live=lambda: False)
    mon.failed(SessionError("model error: x"))
    rig = FaultRig(mon, spool, [])
    (entry,) = entries(rig)
    assert entry["kind"] == model_fault.ERROR_KIND
    assert entry["error"].startswith("SessionError: model error")


def test_a_stub_harness_model_error_never_reaches_the_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 2026-11-27 case: ``lc_live_e2e.sh`` with a stub API filed a 404."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("TUTOR_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:36191")
    notices: list[str] = []
    mon = model_fault.Monitor(notify=lambda: notices.append("toast"))
    mon.failed(
        SessionError(
            "model error: success None There's an issue with the selected model"
            " (claude-sonnet-5-5). It may not exist or you may not have access."
        )
    )
    mon.stderr_line(FENCE)
    assert notices == []
    assert not (tmp_path / "app-errors-spool").exists()
