# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Repair a module whose cards drifted off topic: suspend them, draft more.

``python -m tutor regenerate SUBJECT MODULE [--data DIR] [--now]`` runs the
per-card relevance gate (``judge.gate``) over the module's live cards,
suspends the refused ones (never deletes: ids stay stable, the review queue
skips them) and puts the module back to ``generating``. The worker's next
sync then drafts replacements with ``cardgen.generate`` and publishes them;
``--now`` generates in this process instead (a data dir no worker serves).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import cardgen, judge, wiki
from tutor.curriculum.context import Context
from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.subject_store import LOCK, Change
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.curriculum.records import CardRec

_logger = logging.getLogger(__name__)
_DONE: Final = ("ready", "mastered", "failed")


def _title(url: str) -> str:
    found = wiki.article(url)
    return found[1] if found else url


def regenerate(ctx: Context, subject: str, module_id: str) -> dict[str, Any]:
    """Gate the module's live cards, suspend the refused, set ``generating``."""
    meta = ctx.subjects.need_meta(subject)
    plan = ctx.subjects.plan(subject)
    module = plan.module(module_id) if plan else None
    if plan is None or plan.status != "approved" or module is None:
        msg = f"{subject}/{module_id} is not a module of an approved plan"
        raise RequestError(BAD_REQUEST, msg)
    if module.status not in _DONE:
        msg = f"{subject}/{module_id} is {module.status}, not {'/'.join(_DONE)}"
        raise RequestError(BAD_REQUEST, msg)
    live: dict[str, CardRec] = {
        cid: c
        for cid, c in ctx.subjects.cards(subject).items()
        if c.module == module_id and not c.suspended
    }
    titles = {c.source: _title(c.source) for c in live.values()}
    kept, refused = judge.gate(ctx, meta, module, live, titles)
    gone = [cid for cid in live if cid not in kept]
    with LOCK:  # re-read: the worker may have written meanwhile
        meta = ctx.subjects.need_meta(subject)
        plan = ctx.subjects.plan(subject)
        current = plan.module(module_id) if plan else None
        if plan is None or current is None:
            msg = f"{subject}/{module_id} vanished"
            raise RequestError(BAD_REQUEST, msg)
        cards = ctx.subjects.cards(subject)
        for cid in gone:
            cards[cid].suspended = True
        current.status, current.error = "generating", None
        current.cards = sum(
            c.module == module_id and not c.suspended for c in cards.values()
        )
        ctx.subjects.commit(subject, meta, Change(plan=plan, cards=cards))
    return {"suspended": gone, "why": refused, "kept": list(kept)}


def main(argv: list[str], make: Callable[[Path], Context] = Context) -> int:
    """CLI: ``regenerate SUBJECT MODULE [--data DIR] [--now]``."""
    parser = argparse.ArgumentParser(
        prog="python -m tutor regenerate", description=__doc__
    )
    parser.add_argument("subject")
    parser.add_argument("module")
    parser.add_argument("--data", type=Path, default=None, help="data dir")
    parser.add_argument("--now", action="store_true", help="generate here")
    args = parser.parse_args(argv)
    ctx = make(args.data or data_dir())
    try:
        out = regenerate(ctx, args.subject, args.module)
    except RequestError as err:
        _logger.warning("regenerate refused: %s", err.message)
        print(f"refused: {err.message}")
        return 2
    if args.now:
        out["generate"] = cardgen.generate(ctx, args.subject, args.module)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0
