# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor redraft start|status|drain|report|deck [--data DIR]``.

``start``: back up ``subjects/``, snapshot every subject and queue the units
(``--replies DIR``: replay another run's model replies, e.g. a dry run's).
On the live data dir the running server drains the queue by itself and
waits while a reply is in flight. ``status``: one line per unit; exit 75
while any is pending, 1 when one failed, 0 when all are done. ``drain``:
drain a COPY of the data dir in this process until nothing is pending (the
dry run; it refuses the live data dir, which only the server may drain).
``report``: write the report file and print its path. ``deck``: rewrite the
repo's ``automation`` deck (``--out DIR``: another deck dir) from the
subject as it is now (``deck.export``). Each of ``start``,
``status`` and ``report`` returns in seconds.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING, Final

from tutor import cards
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.curriculum.redraft import deck, drain, report, run
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable

PENDING_EXIT: Final = 75
RETRY_S: Final = 120.0
_logger = logging.getLogger(__name__)


def _status(ctx: Context) -> int:
    found = run.units(ctx)
    for unit in found:
        note = f" ({unit.error})" if unit.error else ""
        print(f"{unit.state:8} {unit.name}{note}")
    states = [u.state for u in found]
    if run.PENDING in states:
        return PENDING_EXIT
    return 1 if run.FAILED in states else 0


def _drain(ctx: Context, workers: int, sleep: Callable[[float], None]) -> int:
    live = Path.home() / ".local/share/tutor"  # what ``tutor.service`` serves
    if ctx.data_dir.resolve() == live.resolve():
        print("refused: only the running server drains the live data dir")
        return 2
    while run.pending(ctx):
        ended = drain.drain(ctx, workers=workers)
        if not ended or any(u.state == run.PENDING for u in ended):
            sleep(RETRY_S)  # another drainer, an outage or a retry: give it time
    return _status(ctx)


def main(
    argv: list[str],
    make: Callable[[Path], Context] = Context,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """CLI entry (``__main__.TOOLS``)."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor redraft", description=__doc__
    )
    parser.add_argument(
        "action", choices=("start", "status", "drain", "report", "deck")
    )
    parser.add_argument("--data", type=Path, default=None, help="data dir")
    parser.add_argument("--replies", type=Path, default=None, help="replies to replay")
    parser.add_argument("--only", action="append", default=[], help="subject/module")
    parser.add_argument("--workers", type=int, default=drain.WORKERS)
    parser.add_argument(
        "--out", type=Path, default=None, help="report file, or the deck dir"
    )
    args = parser.parse_args(argv)
    ctx = make(args.data or data_dir())
    try:
        if args.action == "start":
            found = run.start(ctx, args.replies, frozenset(args.only))
            print(f"queued {len(found)} units in {run.root(ctx)}")
            return 0
        if args.action == "status":
            return _status(ctx)
        if args.action == "drain":
            return _drain(ctx, args.workers, sleep)
        if args.action == "deck":
            done = deck.export(ctx, args.out or cards.DECK_DIR)
            print(json.dumps(done))
            return 0
        print(report.write(ctx, args.out))
    except RequestError as err:
        _logger.warning("redraft %s refused: %s", args.action, err.message)
        print(f"refused: {err.message}")
        return 2
    return 0
