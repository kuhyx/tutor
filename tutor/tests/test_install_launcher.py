# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``install.sh --launcher-only``: ``tutor`` runs the live release's run.sh."""

from __future__ import annotations

from pathlib import Path
import stat
import subprocess

INSTALL = Path(__file__).resolve().parents[2] / "install.sh"


def test_launcher_runs_the_live_release_from_any_directory(tmp_path: Path) -> None:
    release = tmp_path / ".local/lib/tutor-live/current"
    release.mkdir(parents=True)
    stub = release / "run.sh"
    stub.write_text('#!/bin/sh\necho "ran $*"\n', encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    env = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    subprocess.run(
        [str(INSTALL), "--launcher-only"], env=env, check=True, capture_output=True
    )
    launcher = tmp_path / ".local/bin/tutor"
    assert launcher.stat().st_mode & stat.S_IXUSR
    other = tmp_path / "elsewhere"
    other.mkdir()
    done = subprocess.run(
        [str(launcher), "--no-open"],
        env=env,
        cwd=other,
        check=True,
        capture_output=True,
        text=True,
    )
    assert done.stdout.strip() == "ran --no-open"
