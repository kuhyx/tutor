# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor postmortem UNIT [--dry-run [auto|run]] [--retry]``.

- ``--dry-run`` (``auto``): print the analysis of the guard's dry-run request,
  starting it first when needed (75 = pending: call again). ``run`` is the
  started unit's body. Nothing is written but ``postmortems/dry/<unit>.json``.
- ``--retry``: remove the unit's failed markers, so the worker's next tick
  runs the post-mortem again (the failure task's command).
"""

from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING

from tutor.curriculum.context import Context
from tutor.postmortem import dry, files
from tutor.store import data_dir

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def retry(unit: str) -> int:
    """Clear the failed markers of ``unit``; prints how many."""
    folder = files.root() / "failed"
    gone = sorted(folder.glob(f"{files.safe(unit)}-*.json")) if folder.is_dir() else []
    for path in gone:
        path.unlink()
    print(f"queued: {len(gone)} failed marker(s) cleared; the worker runs {unit} next")
    return 0


def main(argv: list[str], make: Callable[[Path], Context] = Context) -> int:
    """CLI entry (``tutor.__main__.TOOLS``)."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor postmortem", description=__doc__
    )
    parser.add_argument("unit")
    parser.add_argument("--dry-run", nargs="?", const="auto", choices=["auto", "run"])
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args(argv)
    try:
        files.safe(args.unit)
    except ValueError as err:
        _logger.warning("post-mortem CLI refused: %s", err)
        print(f"refused: {err}")
        return 2
    if args.retry:
        return retry(args.unit)
    if args.dry_run == "run":
        return dry.work(make(data_dir()), args.unit)
    if args.dry_run == "auto":
        return dry.auto(args.unit)
    parser.print_usage()
    return 2
