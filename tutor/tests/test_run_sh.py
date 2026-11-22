# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``run.sh --route``: open the desktop app on a deep link (stubbed browser)."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import time

import pytest

RUN = Path(__file__).resolve().parents[2] / "run.sh"
APP = "http://127.0.0.1:8778/app/"


def _stub(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run(tmp_path: Path, *args: str, **extra: str) -> list[str]:
    """Run run.sh with a live-server stub; the browser stub logs its argv."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "browser.log"
    _stub(bindir / "curl", "exit 0")  # the server "answers"
    _stub(tmp_path / "browser", f'echo "$@" >> "{log}"')
    env = {
        "PATH": f"{bindir}:/usr/bin:/bin",
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
    while not log.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_route_is_appended_to_the_app_url(tmp_path: Path) -> None:
    [line] = _run(tmp_path, "--route", "/focus?start=1")
    assert f"--app={APP}#/focus?start=1" in line.split()
    assert "--class=tutor" in line
    assert "--user-data-dir=" in line


def test_without_a_route_the_plain_app_opens(tmp_path: Path) -> None:
    [line] = _run(tmp_path)
    assert f"--app={APP}" in line.split()


def test_a_sandbox_port_replaces_the_live_one(tmp_path: Path) -> None:
    [line] = _run(tmp_path, "--route", "/learn/s/m", TUTOR_DESKTOP_PORT="20123")
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
