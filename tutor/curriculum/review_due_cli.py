# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor review-due SUBJECT [--data DIR]``: re-publish its due rows.

Writes the rows of ``review_due.json`` (``DOCS-contract-review-due.md``) that
differ from the log as it is now, and nothing else. ``run.sh`` runs it when
the lock opens ``/review/<subject>/<module>``: a failed write leaves a stale
file that can read more due than is true, and the window would then show
nothing to review while the lock still asks for one. A failure is logged at
warning (to stderr, as no handler is set) and exits 1; ``run.sh`` appends
both to the server log.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import time

from tutor.curriculum import module_state, review_due
from tutor.ledger_io import LedgerError
from tutor.store import data_dir

_logger = logging.getLogger(__name__)


def main(argv: list[str]) -> int:
    """CLI: re-publish ``SUBJECT``'s rows; 1 when the file could not be written."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor review-due", description=__doc__
    )
    parser.add_argument("subject")
    parser.add_argument("--data", type=Path, default=None, help="data dir")
    args = parser.parse_args(argv)
    if args.subject not in module_state.SUBJECTS:
        return 0  # no due file for it: nothing to heal
    try:
        review_due.reconcile(args.data or data_dir(), args.subject, time.time())
    except (OSError, ValueError, LedgerError) as exc:
        _logger.warning("review due of %s not recorded: %s", args.subject, exc)
        return 1
    return 0
