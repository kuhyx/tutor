# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker's post-mortem tick: notice a finished unit, analyse it once, apply.

A unit is due when its latest verified C6 row (``unit_finish.json``, signed
by leetcode-guard) claims at least :data:`MIN_NEW` solves no earlier
post-mortem of it saw. A finish after the re-pass adds no solve, so it starts
nothing (no loop). It also waits for the code of every claimed solve
(``history/<slug>.json``), at most :data:`evidence.CODE_WAIT_S` after the row:
the solve that finished the unit may not be mirrored yet.

One draft-tier call, no retry: a failure logs a warning, writes nothing but
the failed marker of that revision (every later tick skips it) and files
``Post-mortem <unit> failed`` at once; ``--retry`` removes the marker. A
success applies the card changes, saves the signed report, the C7 row and
the lessons, and files the approval task.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.errors import RequestError
from tutor.postmortem import (
    apply,
    evidence,
    files,
    lessons,
    proposal,
    report,
    run,
    signed,
    todo,
)

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.postmortem.evidence import Request

_logger = logging.getLogger(__name__)
MIN_NEW: Final = 3
ERRORS: Final = (RequestError, OSError, ValueError, LookupError, TypeError)


def requests() -> list[Request]:
    """The latest verified C6 request per unit, in file order."""
    rows = signed.verified_rows(files.finish_path(), files.FINISH_KIND) or []
    latest: dict[str, Request] = {}
    for row in rows:
        found = evidence.parse_request(row)
        if found is not None:
            latest[found.unit] = found
    return list(latest.values())


def due(now: float) -> tuple[Request, int] | None:
    """The first unit owed a post-mortem now, and its revision number."""
    for found in requests():
        unseen = set(found.solves) - report.seen(found.subject, found.unit)
        if len(unseen) < MIN_NEW:
            continue
        rev = len(report.revisions(found.subject, found.unit)) + 1
        if files.failed_path(found.unit, rev).exists():
            continue
        ready = all(evidence.has_code(slug) for slug in found.solves)
        if not ready and now - found.at < evidence.CODE_WAIT_S:
            continue
        return found, rev
    return None


def _fail(found: Request, rev: int, err: Exception) -> str:
    marker = files.failed_path(found.unit, rev)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"rev": rev, "error": str(err)}), encoding="utf-8")
    todo.queue(
        f"failed-{found.unit}-{rev}",
        proposal.failed_title(found.unit),
        proposal.failed_body(found.unit, rev, str(err)),
    )
    return "failed"


def perform(ctx: Context, found: Request, rev: int) -> dict[str, Any]:
    """Analyse, apply and record revision ``rev``; returns the saved entry.

    The revision is stamped BEFORE the model call and the apply: the guard pays
    the re-pass only for a ``done: false`` signed after ``at``, and the apply's
    own un-teaching is that row.
    """
    at = ctx.clock() / 1000
    analysis = run.analyse(ctx, found)
    applied = apply.apply(ctx, analysis, rev)
    entry = {**analysis, "rev": rev, "at": at, "applied": applied}
    entry["earlier"] = report.earlier(found.unit)
    report.save(found.subject, found.unit, entry)
    report.record_revision(analysis, rev, at)
    keep = {"unit": found.unit, "rev": rev, "at": at, **analysis["lessons"]}
    lessons.record(found.subject, keep)
    todo.queue(
        f"apply-{found.unit}-{rev}",
        proposal.apply_title(found.unit),
        proposal.apply_body(entry),
    )
    return entry


def tick(ctx: Context, now: float) -> str:
    """One round: file queued tasks, run the post-mortem owed, file again."""
    todo.flush()
    owed = due(now)
    if owed is None:
        return "idle"
    found, rev = owed
    try:
        perform(ctx, found, rev)
        outcome = "done"
    except ERRORS as err:
        _logger.warning("post-mortem of %s failed: %s", found.unit, err)
        outcome = _fail(found, rev, err)
    todo.flush()
    return outcome
