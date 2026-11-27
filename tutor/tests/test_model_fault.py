# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A model sandbox that will not start: one icon-only toast and one board entry."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ProcessError

from tutor import model_fault
from tutor.outage import ClaudeUnavailableError
from tutor.session import SessionError

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.tests.conftest import FaultRig

FENCE = "tutor_model_netfence: the egress filter did not load; not starting"


def entries(rig: FaultRig) -> list[dict[str, Any]]:
    """The spool lines written so far."""
    path = rig.spool / "tutor.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_fence_line_files_one_entry_and_one_toast(fault: FaultRig) -> None:
    fault.monitor.stderr_line(FENCE)
    (entry,) = entries(fault)
    assert entry["kind"] == model_fault.SANDBOX_KIND
    assert entry["repo"] == "kuhyx/tutor"
    assert entry["error"].startswith("SandboxStartError: tutor_model_netfence")
    assert len(fault.notices) == 1


def test_the_sandbox_script_own_failures_count_too(fault: FaultRig) -> None:
    fault.monitor.stderr_line("tutor_model_sandbox: bwrap not found")
    assert len(entries(fault)) == 1
    assert len(fault.notices) == 1


def test_other_stderr_is_ignored(fault: FaultRig) -> None:
    fault.monitor.stderr_line("warning: something else")
    assert entries(fault) == []
    assert fault.notices == []


def test_a_streak_notifies_once_until_a_call_succeeds(fault: FaultRig) -> None:
    fault.monitor.stderr_line(FENCE)
    fault.monitor.stderr_line(FENCE)
    fault.monitor.failed(ProcessError("cli exited", exit_code=1))
    assert len(entries(fault)) == 1
    assert len(fault.notices) == 1
    fault.monitor.succeeded()
    fault.monitor.stderr_line(FENCE)
    assert len(fault.notices) == 2


def test_any_other_model_error_is_filed_without_a_toast(fault: FaultRig) -> None:
    fault.monitor.failed(SessionError("model error: error_during_execution"))
    (entry,) = entries(fault)
    assert entry["kind"] == model_fault.ERROR_KIND
    assert entry["error"].startswith("SessionError: model error")
    assert fault.notices == []


def test_a_fence_line_after_a_plain_error_still_toasts(fault: FaultRig) -> None:
    fault.monitor.failed(ProcessError("cli exited", exit_code=1))
    fault.monitor.stderr_line(FENCE)
    assert [e["kind"] for e in entries(fault)] == [
        model_fault.ERROR_KIND,
        model_fault.SANDBOX_KIND,
    ]
    assert len(fault.notices) == 1


def test_an_outage_is_not_a_fault(fault: FaultRig) -> None:
    fault.monitor.failed(ClaudeUnavailableError("rate_limit", 5))
    assert entries(fault) == []
    assert fault.notices == []


def test_the_message_is_one_short_line(fault: FaultRig) -> None:
    fault.monitor.failed(SessionError("first\n" + "x" * 500))
    (entry,) = entries(fault)
    assert "\n" not in entry["error"]
    assert len(entry["error"]) < 200


def test_the_toast_is_an_icon_and_a_glyph_only() -> None:
    argv = model_fault.notify_argv("/usr/bin/notify-send")
    assert argv[0] == "/usr/bin/notify-send"
    assert argv[argv.index("-i") + 1] == "system-reboot"
    assert argv[argv.index("-u") + 1] == "critical"
    summary = argv[-1]
    assert summary
    assert not any(ch.isalnum() for ch in summary)  # a pictogram, no words


def test_send_runs_notify_send_and_never_raises() -> None:
    ran: list[list[str]] = []

    def run(argv: list[str], **_: object) -> None:
        ran.append(argv)

    model_fault.send_toast(run=run, which=lambda _: "/usr/bin/notify-send")
    assert ran == [model_fault.notify_argv("/usr/bin/notify-send")]
    model_fault.send_toast(run=run, which=lambda _: None)  # headless: skipped
    assert len(ran) == 1

    def boom(argv: list[str], **_: object) -> None:
        raise subprocess.TimeoutExpired(argv, 10)

    model_fault.send_toast(run=boom, which=lambda _: "/usr/bin/notify-send")


def test_the_real_spool_is_never_the_default_in_tests(tmp_path: Path) -> None:
    mon = model_fault.Monitor()
    assert mon.spool is None  # resolved lazily, by the reporter, at first use
    assert model_fault.MONITOR.notify is not model_fault.send_toast


def test_the_default_spool_is_the_users_app_errors_spool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    model_fault.Monitor(notify=lambda: None, live=lambda: True).stderr_line(FENCE)
    assert (tmp_path / "state" / "app-errors-spool" / "tutor.jsonl").is_file()


def test_a_broken_reporter_or_toast_never_reaches_the_model_path(
    fault: FaultRig, caplog: pytest.LogCaptureFixture
) -> None:
    class Broken:
        def report(self, kind: str, error: object) -> None:
            msg = f"spool is gone: {kind} {error}"
            raise OSError(msg)

    def no_toast() -> None:
        msg = "no bus"
        raise OSError(msg)

    mon = model_fault.Monitor(notify=no_toast, live=lambda: True)
    mon._reporter = Broken()
    mon.stderr_line(FENCE)
    mon.succeeded()
    mon.failed(SessionError("x"))
    assert "model fault not reported" in caplog.text
    assert "toast failed" in caplog.text
