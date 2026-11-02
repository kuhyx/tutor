# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor sql-cards``: seed the bank's SQL cards into a subject.

The backfill for lessons learned before the server seeded them itself. Cards
are taught ``--taught-days-ago`` days back (default 3: a first FSRS review
falls due about 2 days after teaching). Try it on a copy of the data dir
first (``--data``): on the live one this writes the subject files and
``log.jsonl`` from outside the server's process (atomic writes, but no shared
lock), so back them up.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tutor.curriculum import sql_cards
from tutor.curriculum.context import Context
from tutor.curriculum.sql_engine import run_query
from tutor.store import data_dir

DAY_MS = 86_400_000


def main(argv: list[str]) -> int:
    """Seed every concept; print ``{"added","taught","skipped"}``; 1 if any skipped."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor sql-cards", description=__doc__
    )
    parser.add_argument("--data", type=Path, default=None, help="data dir")
    parser.add_argument("--subject", default=sql_cards.SUBJECT)
    parser.add_argument("--taught-days-ago", type=float, default=3.0)
    args = parser.parse_args(argv)
    ctx = Context(args.data or data_dir())
    at = ctx.clock() - int(args.taught_days_ago * DAY_MS)
    got = sql_cards.seed_all(ctx, run_query, subject=args.subject, taught_at=at)
    sys.stdout.write(json.dumps(got.__dict__, indent=1) + "\n")
    return 1 if got.skipped else 0
