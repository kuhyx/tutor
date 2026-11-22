# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``run.sh --route``: open the desktop app on a deep link (stubbed browser)."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

import pytest

RUN = Path(__file__).resolve().parents[2] / "run.sh"
APP = "http://127.0.0.1:8778/app/"
FOCUS = 'i3-msg [class="^tutor$"] focus'


def _stub(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run(
    tmp_path: Path, *args: str, i3: str | None = "exit 0", **extra: str
) -> list[str]:
    """Run run.sh with a live-server stub; the stubs log their argv, in call order.

    ``i3-msg`` is a stub that logs and then runs ``i3`` (never kuhy's i3);
    ``i3=None`` is a PC without i3: PATH holds only what run.sh itself needs.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "browser.log"
    _stub(bindir / "curl", "exit 0")  # the server "answers"
    _stub(tmp_path / "browser", f'echo "$@" >> "{log}"')
    if i3 is None:
        for tool in ("dirname", "mkdir", "setsid", "timeout"):
            (bindir / tool).symlink_to(shutil.which(tool) or f"/usr/bin/{tool}")
    else:
        _stub(bindir / "i3-msg", f'echo "i3-msg $@" >> "{log}"\n{i3}')
    env = {
        "PATH": str(bindir) if i3 is None else f"{bindir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "TUTOR_BROWSER": str(tmp_path / "browser"),
        "TUTOR_DESKTOP_PROFILE": str(tmp_path / "profile"),
        **extra,
    }
    done = subprocess.run(
        [str(RUN), *args], env=env, capture_output=True, timeout=30, check=False
    )
    assert done.returncode == 0, done.stderr
    deadline = time.monotonic() + 5  # setsid -f detaches the browser
    while "--app=" not in _text(log) and time.monotonic() < deadline:
        time.sleep(0.02)
    return _text(log).splitlines()


def _text(log: Path) -> str:
    return log.read_text(encoding="utf-8") if log.exists() else ""


def test_route_is_appended_to_the_app_url(tmp_path: Path) -> None:
    [line] = _run(tmp_path, "--route", "/focus?start=1")  # one line: i3 not asked
    assert f"--app={APP}#/focus?start=1" in line.split()
    assert "--class=tutor" in line
    assert "--user-data-dir=" in line


def test_without_a_route_the_plain_app_opens(tmp_path: Path) -> None:
    [line] = _run(tmp_path)
    assert f"--app={APP}" in line.split()


@pytest.mark.parametrize("route", ["/learn/s/m", "/review/s/m", "/rework/s/m/x"])
def test_a_handed_route_shows_the_open_window_first(tmp_path: Path, route: str) -> None:
    """i3 focuses the open tutor window before the browser hands the route over."""
    [focus, opened] = _run(tmp_path, "--route", route)
    assert focus == FOCUS
    assert f"--app={APP}#{route}" in opened.split()


@pytest.mark.parametrize("i3", ["exit 2", "exec sleep 20", None])
def test_a_learn_route_opens_whatever_i3_does(tmp_path: Path, i3: str | None) -> None:
    """No tutor window to focus, an i3 that hangs, or no i3: the app still opens."""
    lines = _run(tmp_path, "--route", "/learn/s/m", i3=i3)
    assert lines[:-1] == ([] if i3 is None else [FOCUS])
    assert f"--app={APP}#/learn/s/m" in lines[-1].split()


def test_a_sandbox_port_replaces_the_live_one(tmp_path: Path) -> None:
    *_, line = _run(tmp_path, "--route", "/learn/s/m", TUTOR_DESKTOP_PORT="20123")
    assert "--app=http://127.0.0.1:20123/app/#/learn/s/m" in line.split()


def test_a_dead_sandbox_port_starts_nothing(tmp_path: Path) -> None:
    """A sandbox that is down is an error; tutor.service is not started for it."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    started = tmp_path / "systemctl.log"
    _stub(bindir / "curl", "exit 7")  # nothing listens
    _stub(bindir / "systemctl", f'echo "$@" >> "{started}"')
    done = subprocess.run(
        [str(RUN), "--no-open"],
        env={
            "PATH": f"{bindir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "TUTOR_DESKTOP_PORT": "20123",
        },
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 1
    assert b"20123" in done.stderr
    assert not started.exists()


@pytest.mark.parametrize("bad", ["focus", "//evil.example/x", "/a b", "/x\ny"])
def test_a_route_must_be_a_rooted_path(tmp_path: Path, bad: str) -> None:
    done = subprocess.run(
        [str(RUN), "--route", bad, "--no-open"],
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert done.returncode != 0


def _heal(tmp_path: Path, *args: str, body: str = "exit 0", **extra: str) -> list[str]:
    """Run run.sh with a ``TUTOR_PYTHON`` stub; its calls as ``cwd: argv`` lines."""
    release = tmp_path / ".local" / "lib" / "tutor-live" / "current"
    release.mkdir(parents=True)
    calls = tmp_path / "python.log"
    py = tmp_path / "python"
    _stub(py, f'echo "$(pwd): $@" >> "{calls}"\n{body}')
    _run(tmp_path, *args, TUTOR_PYTHON=str(py), **extra)
    deadline = time.monotonic() + 5  # setsid -f detaches the republish
    while not calls.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    return _text(calls).splitlines()


def test_a_review_route_republishes_that_subjects_due_rows(tmp_path: Path) -> None:
    """The live release's interpreter runs ``review-due`` for the route's subject."""
    release = tmp_path / ".local" / "lib" / "tutor-live" / "current"
    assert _heal(tmp_path, "--route", "/review/s/m") == [
        f"{release}: -m tutor review-due s"
    ]


@pytest.mark.parametrize("route", ["/learn/s/m", "/review", "/review/s", "/focus"])
def test_other_routes_republish_nothing(tmp_path: Path, route: str) -> None:
    assert _heal(tmp_path, "--route", route) == []


def test_a_sandbox_port_republishes_nothing(tmp_path: Path) -> None:
    """A sandbox server never touches the live data dir."""
    got = _heal(tmp_path, "--route", "/review/s/m", TUTOR_DESKTOP_PORT="20123")
    assert got == []


def test_a_slow_republish_never_delays_the_window(tmp_path: Path) -> None:
    started = time.monotonic()
    _heal(tmp_path, "--route", "/review/s/m", body="sleep 3")
    assert time.monotonic() - started < 2.5


def test_a_failed_republish_is_logged_and_the_window_still_opens(
    tmp_path: Path,
) -> None:
    got = _heal(
        tmp_path,
        "--route",
        "/review/s/m",
        body='echo "not recorded: disk full" >&2\nexit 1',
    )
    assert got
    log = tmp_path / ".local" / "state" / "tutor" / "server.log"
    deadline = time.monotonic() + 5
    while "disk full" not in _text(log) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert "disk full" in _text(log)
    assert "--app=" in _text(tmp_path / "browser.log")


def test_the_default_interpreter_is_the_one_the_service_runs() -> None:
    """The frozen release has no .venv: run.sh must name tutor.service's python."""
    unit = (RUN.parent / "systemd" / "tutor.service").read_text(encoding="utf-8")
    exec_start = next(
        line.split("=", 1)[1]
        for line in unit.splitlines()
        if line.startswith("ExecStart=")
    )
    service_python = exec_start.split()[0].replace("%h", "$HOME")
    assert f"${{TUTOR_PYTHON:-{service_python}}}" in RUN.read_text(encoding="utf-8")
