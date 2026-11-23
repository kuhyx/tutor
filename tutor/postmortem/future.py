# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor apply-postmortem UNIT [--module M ...]``: the approved part.

Run after kuhy approves the task ``Apply post-mortem <unit>: future modules +
skills`` (its spec stage is the approval). For each future module the latest
revision of the unit's signed report proposed (``--module`` keeps only those
named): a module with no taught card is regenerated (``regen.regenerate``:
off-topic untaught cards suspended, the worker drafts again, and the drafter
already reads ``lessons.json``), then every proposed card is added on its own
seeded source (``apply.seeded``). A taught module only gains the cards.
The skill proposals are not applied here: a normal session edits skills.
"""

from __future__ import annotations

import argparse
import logging
from typing import TYPE_CHECKING, Any

from tutor.curriculum import card_ops, regen
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.postmortem import apply, report
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_logger = logging.getLogger(__name__)


def latest(unit: str) -> dict[str, Any] | None:
    """The unit's latest signed revision, with its ``subject``; ``None``: no report."""
    for doc in report.everything():
        found = [r for r in doc.get("revisions") or [] if isinstance(r, dict)]
        if doc.get("unit") == unit and found:
            return {**found[-1], "subject": doc.get("subject")}
    return None


def _module(ctx: Context, entry: dict[str, Any], future: dict[str, Any]) -> str:
    subject, module = str(entry["subject"]), str(future["module"])
    taught = ctx.fold().taught_ids(subject)
    mine = [c for c, r in ctx.subjects.cards(subject).items() if r.module == module]
    parts = []
    if not any(c in taught for c in mine):
        regen.regenerate(ctx, subject, module)
        parts.append("regenerated")
    added = 0
    for card in future.get("cards") or []:
        front, back = str(card.get("front") or ""), str(card.get("back") or "")
        where = (f"{entry['unit']}-future", int(entry["rev"]))
        draft = apply.seeded_draft(where, module, front, back, "postmortem-future")
        try:
            card_ops.add(ctx, subject, draft)
        except RequestError as err:
            _logger.warning("apply-postmortem: %r not added: %s", front, err.message)
            continue
        added += 1
    return f"{module}: {' + '.join([*parts, f'{added} card(s)'])}"


def run(ctx: Context, unit: str, only: list[str]) -> list[str]:
    """Apply the future part of ``unit``'s latest revision; one line per module."""
    entry = latest(unit)
    if entry is None:
        return []
    return [
        _module(ctx, entry, future)
        for future in entry.get("future") or []
        if isinstance(future, dict) and (not only or future.get("module") in only)
    ]


def main(argv: list[str], make: Callable[[Path], Context] = Context) -> int:
    """CLI entry (``tutor.__main__.TOOLS``): 0, or 1 when there is no report."""
    parser = argparse.ArgumentParser(prog="python -m tutor apply-postmortem")
    parser.add_argument("unit")
    parser.add_argument("--module", action="append", default=[])
    args = parser.parse_args(argv)
    lines = run(make(data_dir()), args.unit, args.module)
    if not lines:
        print(f"nothing applied: no signed post-mortem proposal for {args.unit}")
        return 1
    print("\n".join(lines))
    return 0
