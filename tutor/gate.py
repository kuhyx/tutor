# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor.gate --production --evening``: the tutor's evening gate.

One rung of the evening chain (gatelock.evening_chain): paid today exits 0 with
no window; otherwise a HARD lock window runs until the credit lands (exit 0) or
kuhy ends the evening (exit 10). No X within 10 s exits 3. Read-only: it never
writes the ledger.

Runs under ``/usr/bin/python3``: this module and what it imports are stdlib +
``gatelock`` + ``earned_time`` only, never the tutor's venv-only dependencies
(``tutor/__init__.py`` is empty). Install: see ``DOCS-evening-gate.md``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING, Any, Final

import gatelock

from tutor import gate_lock
from tutor.gate_state import local_today, read_progress
from tutor.ledger_io import Paths, default_paths

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

EXIT_NO_X: Final = 3
EXIT_USAGE: Final = 2
X_WAIT_SECONDS: Final = 10.0
end_evening_code: Final = gate_lock.end_evening_code
_logger: Final = logging.getLogger(__name__)


def run_evening(
    paths: Paths,
    *,
    production: bool,
    today: date | None = None,
    wait_x: Callable[..., bool] = gatelock.wait_for_x_server,
    lock_factory: Callable[..., Any] | None = None,
) -> int:
    """Decide, wait for X (bounded), lock until paid or ended; the exit code."""
    day = today or local_today()
    progress = read_progress(paths, day)
    if progress is not None and progress.paid:
        _logger.info("tutor quota paid today (%d min); no window", progress.minutes)
        return 0
    if not wait_x(timeout_s=X_WAIT_SECONDS):
        _logger.error("no X server within %.0f s; no window", X_WAIT_SECONDS)
        return EXIT_NO_X
    factory = lock_factory or gate_lock.EveningLock
    lock = factory(
        paths,
        progress,
        today=(lambda: today) if today else local_today,
        production=production,
    )
    lock.run()
    return int(lock.exit_code)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run. Only ``--evening`` exists; the morning is not here."""
    parser = argparse.ArgumentParser(prog="python -m tutor.gate")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--evening", action="store_true")
    args = parser.parse_args(argv)
    if not args.evening:
        sys.stderr.write("usage: python -m tutor.gate [--production] --evening\n")
        return EXIT_USAGE
    logging.basicConfig(level=logging.INFO, format="tutor.gate: %(message)s")
    return run_evening(default_paths(), production=args.production)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
