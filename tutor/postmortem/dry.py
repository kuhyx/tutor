# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The dry run: the analysis of a unit's solves so far, with nothing written.

leetcode-guard's ``--postmortem-dry-run UNIT`` signs a ``unit_preview`` row
(``postmortem_dry_run.json``) and calls ``python -m tutor postmortem UNIT
--dry-run``. A draft-tier call outlives the 60 s action cap, so ``auto``
starts the work as a ``systemd-run --user`` unit and answers 75 (pending)
until the result for THAT request is on file. The work (``run``) writes only
``postmortems/dry/<unit>.json``: no card, log event, report, lesson or task.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.errors import RequestError
from tutor.postmortem import evidence, files, run, show, signed

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.curriculum.context import Context

_logger = logging.getLogger(__name__)
PENDING: Final = 75
ENV_KEYS: Final = ("TUTOR_DATA", "TUTOR_KEY", "TUTOR_GUARD_DATA", "HOME")
type Runner = Callable[[list[str]], int]


def unit_name(unit: str) -> str:
    """The systemd unit that runs ``unit``'s dry run."""
    return f"tutor-postmortem-dry-{files.safe(unit)}"


def _subprocess(argv: list[str]) -> int:
    done = subprocess.run(argv, check=False, capture_output=True, text=True)
    return done.returncode


def request(unit: str) -> evidence.Request | None:
    """The guard's signed dry-run request for ``unit``, if any."""
    rows = signed.verified_rows(files.preview_path(), files.PREVIEW_KIND) or []
    found = [evidence.parse_request(r) for r in rows]
    mine = [r for r in found if r and r.unit == unit]
    return mine[-1] if mine else None


def _result(unit: str) -> dict[str, Any] | None:
    path = files.dry_path(unit)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        _logger.warning("post-mortem dry run: no result for %s yet: %s", unit, err)
        return None
    return raw if isinstance(raw, dict) else None


def _save(unit: str, body: dict[str, Any]) -> None:
    path = files.dry_path(unit)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=1), encoding="utf-8")
    tmp.replace(path)


def work(ctx: Context, unit: str) -> int:
    """Analyse the request now (the systemd unit's body); prints the report."""
    found = request(unit)
    if found is None:
        print(f"no signed dry-run request for {unit}")
        return 2
    try:
        analysis = run.analyse(ctx, found)
    except (RequestError, OSError, ValueError) as err:
        _logger.warning("post-mortem dry run of %s failed: %s", unit, err)
        _save(unit, {"request_at": found.at, "error": str(err)})
        print(f"failed: {err}")
        return 1
    _save(unit, {"request_at": found.at, "analysis": analysis})
    print(show.text(analysis))
    return 0


def auto(unit: str, runner: Runner = _subprocess) -> int:
    """Print the result for the current request, or start it: 0, 1, 2 or 75."""
    found = request(unit)
    if found is None:
        print(f"no signed dry-run request for {unit}")
        return 2
    result = _result(unit)
    if result is not None and result.get("request_at") == found.at:
        if "error" in result:
            print(f"failed: {result['error']}")
            return 1
        print(show.text(result["analysis"]))
        return 0
    name = unit_name(unit)
    if runner(["systemctl", "--user", "is-active", "--quiet", name]) == 0:
        print(f"pending: {name} is running")
        return PENDING
    env = [f"-E{k}={os.environ[k]}" for k in ENV_KEYS if k in os.environ]
    argv = ["systemd-run", "--user", "--collect", f"--unit={name}"]
    argv += [f"--working-directory={Path.cwd()}", *env]
    argv += [sys.executable, "-m", "tutor", "postmortem", unit, "--dry-run", "run"]
    if runner(argv) != 0:
        print(f"failed: could not start {name}")
        return 1
    print(f"pending: started {name}")
    return PENDING
