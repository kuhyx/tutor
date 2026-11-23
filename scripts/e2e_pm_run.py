#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's phase log: one ``pm-F32-<phase>.log`` of PASS/FAIL lines."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

from e2e_pm_world import BASE

EVIDENCE: Final = Path(os.environ.get("E2E_PM_EVIDENCE") or BASE / "evidence")


class Run:
    """One phase's log and verdicts."""

    def __init__(self, phase: str) -> None:
        """Log to ``pm-F32-<phase>.log`` in :data:`EVIDENCE`."""
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.log = (EVIDENCE / f"pm-F32-{phase}.log").open("w", encoding="utf-8")
        self.failed = 0

    def say(self, line: str) -> None:
        """Print and log one line."""
        print(line, flush=True)
        self.log.write(line + "\n")

    def check(self, ok: object, label: str, detail: object = "") -> None:
        """One verdict line; a failure makes the phase exit 1."""
        self.failed += not ok
        self.say(f"{'PASS' if ok else 'FAIL'} {label}" + ("" if ok else f": {detail}"))

    def show(self, label: str, value: object) -> None:
        """One evidence line (JSON, trimmed)."""
        self.say(f"  {label}: {json.dumps(value, default=str)[:1500]}")
