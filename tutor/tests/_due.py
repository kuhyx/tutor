# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Helpers of the C4 tests (``review_due.json``): rows, a LeetCode subject, events."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tutor.curriculum.eventlog import review_event, worker_event
from tutor.tests._cur import T0, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

LC = "leetcode-easy-algorithms-in-typescript"
JS = "javascript-and-pandas-for-leetcode-easy"
SQL = "mysql-8-for-timed-sql-coding-tests-joins-and"
PHONE = "dev-phone"


def rows_of(root: Path) -> list[dict[str, Any]]:
    """The entries of ``review_due.json`` (none when it is not there)."""
    path = root / "review_due.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    assert raw["version"] == 1
    entries: list[dict[str, Any]] = raw["entries"]
    return entries


def row_of(root: Path, subj: str, mod: str) -> dict[str, Any]:
    """The one row of (subject, module)."""
    (found,) = (
        r
        for r in rows_of(root)
        if (r["detail"]["subject"], r["detail"]["module"]) == (subj, mod)
    )
    return found


def due_of(root: Path, mod: str = "a", subj: str = LC) -> list[int]:
    """The ``due_ms`` of that module's row."""
    listed: list[int] = row_of(root, subj, mod)["detail"]["due_ms"]
    return listed


def make_lc(tmp_path: Path, **found: Any) -> Context:
    """A LeetCode subject with modules a and b and the cards ``found``."""
    ctx, _ = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    subject(ctx, LC, modules=mods, found=found)
    return ctx


def teach(ctx: Context, cid: str, at: int = T0, subj: str = LC) -> None:
    """The worker marks a card taught at ``at``."""
    ctx.log.append([worker_event("taught", (subj, cid), dev=ctx.device, at=at)])


def mirror(ctx: Context, raw: dict[str, Any], eid: str) -> None:
    """An event from the phone, as the relay mirrors it."""
    ctx.log.mirror(PHONE, {eid: raw})


def review(ctx: Context, cid: str, at: int, rating: int = 3) -> None:
    """The phone reviews ``cid`` at ``at`` (Good by default)."""
    event = review_event((LC, cid), rating, dev=PHONE, span=(at - 5, at), rev=1)
    raw = {k: v for k, v in event.items() if k not in {"dev", "eid"}}
    mirror(ctx, raw, event["eid"])
