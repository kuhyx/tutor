#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's guard-side fixtures: the first lock run and kuhy's mirrored code."""

from __future__ import annotations

import os
import shutil
import subprocess

import e2e_pm_reply as canned
from e2e_pm_world import GUARD, LIVE_HISTORY, ROOT, Case


def seed(case: Case) -> str:
    """The guard's first lock run (it creates the ledger, never arms)."""
    read, write = os.pipe()
    xvfb = subprocess.Popen(  # killed by PID below
        [
            shutil.which("Xvfb") or "/usr/bin/Xvfb",
            "-displayfd",
            str(write),
            "-screen",
            "0",
            "1600x1200x24",
            "-nolisten",
            "tcp",
        ],
        pass_fds=(write,),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.close(write)
    display = ":" + os.read(read, 16).decode().strip()
    os.close(read)
    try:
        done = subprocess.run(
            ["/usr/bin/python3", str(ROOT / "scripts/e2e_pm_guard.py"), "lock"],
            cwd=GUARD,
            env=case.guard_env(display=display),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    finally:
        xvfb.terminate()
        xvfb.wait(timeout=5)
    return f"exit {done.returncode} on {display}\n{(done.stdout + done.stderr)[-1500:]}"


def copy_history(case: Case) -> list[str]:
    """Kuhy's mirrored code of the four solves, copied read-only."""
    for slug in canned.SLUGS:
        shutil.copyfile(
            LIVE_HISTORY / f"{slug}.json",
            case.guard_data / "history" / f"{slug}.json",
        )
    return list(canned.SLUGS)
