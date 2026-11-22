# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C2: a module's done / not-done state, one signed row per flip.

leetcode-guard decides from these rows whether a unit's theory is done
(``DOCS-contract-module-state.md``). A module is done when it has at least one
live (not suspended) card and every live card is taught. The latest verified
row per (subject, module) wins; no row means not done.

:class:`WatchedStore` and :class:`WatchedLog` are what ``Context`` hands out,
so every card commit and every ``taught`` / ``untaught`` event of the
:data:`SUBJECTS` re-checks the truth, wherever it came from (teaching, a
generation, a regeneration, a split, an edit, a mirrored event).
:func:`backfill` writes the truth for every module at startup. A failed write
logs a warning and never reaches the caller: the commit or event it follows
has already landed.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any, Final

import earned_time

from tutor.curriculum import review_due
from tutor.curriculum.eventlog import EventLog
from tutor.curriculum.fold import fold
from tutor.curriculum.subject_store import SubjectStore
from tutor.ledger_io import (
    LedgerError,
    default_paths,
    exclusive,
    read_key,
    read_rows,
    write_rows,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path

    from tutor.curriculum.records import Meta
    from tutor.curriculum.subject_store import Change

# The two gated LeetCode subjects and the SQL one (SPEC "Subjects").
SUBJECTS: Final = frozenset(
    {
        "leetcode-easy-algorithms-in-typescript",
        "javascript-and-pandas-for-leetcode-easy",
        "mysql-8-for-timed-sql-coding-tests-joins-and",
    }
)
KIND: Final = "module_state"
VERSION: Final = 1
_TEACHING: Final = frozenset({"taught", "untaught"})
_logger = logging.getLogger(__name__)


def truth(root: Path, subject: str) -> dict[str, bool]:
    """Plan module id -> done, from the cards and the raw (unmasked) log.

    The log is not masked by archiving: hiding a subject is not un-teaching it.
    """
    store = SubjectStore(root)
    plan = store.plan(subject)
    live: dict[str, list[str]] = {m.id: [] for m in plan.modules} if plan else {}
    for cid, rec in store.cards(subject).items():
        if not rec.suspended and rec.module in live:
            live[rec.module].append(cid)
    events = [e for e in EventLog(root).read() if e.get("s") == subject]
    taught = fold(events).taught_ids(subject)
    return {m: bool(ids) and set(ids) <= taught for m, ids in live.items()}


def _latest(rows: list[object], key: bytes) -> dict[tuple[str, str], bool]:
    """(subject, module) -> ``done`` of its last verified row, in file order."""
    out: dict[tuple[str, str], bool] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") != KIND:
            continue
        detail = row.get("detail")
        if isinstance(detail, dict) and earned_time.verified(row, key):
            ref = (str(detail.get("subject")), str(detail.get("module")))
            out[ref] = detail.get("done") is True
    return out


def _row(
    rows: list[object], ref: tuple[str, str], *, done: bool, at: float, key: bytes
) -> dict[str, Any]:
    """The signed row; ``n`` counts every row of ``ref``, verified or not."""
    prefix = f"state:{ref[0]}:{ref[1]}:"
    n = 1 + sum(
        isinstance(r, dict) and str(r.get("entry_id", "")).startswith(prefix)
        for r in rows
    )
    row: dict[str, Any] = {
        "kind": KIND,
        "entry_id": f"{prefix}{n}",
        "day": datetime.fromtimestamp(at, tz=UTC).astimezone().date().isoformat(),
        "detail": {"subject": ref[0], "module": ref[1], "done": done, "at": at},
    }
    row["hmac"] = str(earned_time.entry_signature(row, key))
    return row


def reconcile(
    root: Path, subject: str, at: float, *, backfill_all: bool = False
) -> list[dict[str, Any]]:
    """Append a row for each module whose truth differs from its latest row.

    ``backfill_all`` also writes the truth of a module with no verified row yet.
    Returns the rows written.

    Raises:
        LedgerError: ``module_state.json`` exists but is not a state file.
    """
    key = read_key(default_paths().key_file)
    if key is None:
        _logger.warning("module state of %s not recorded: no signing key", subject)
        return []
    path = root / "module_state.json"
    with exclusive(root / "module_state.lock"):
        rows = read_rows(path)
        latest = _latest(rows, key)
        fresh: list[dict[str, Any]] = []
        for module, done in truth(root, subject).items():
            was = latest.get((subject, module))
            if was == done or (was is None and not done and not backfill_all):
                continue  # no flip (no row already reads as not done)
            ref = (subject, module)
            fresh.append(_row([*rows, *fresh], ref, done=done, at=at, key=key))
        if fresh:
            write_rows(path, [*rows, *fresh], version=VERSION)
    return fresh


def record(root: Path, subject: str, at: float, *, backfill_all: bool = False) -> None:
    """:func:`reconcile`, a failure logged at warning and swallowed."""
    try:
        reconcile(root, subject, at, backfill_all=backfill_all)
    except (OSError, ValueError, LedgerError) as exc:
        _logger.warning("module state of %s not recorded: %s", subject, exc)


def backfill(root: Path, at: float) -> None:
    """Write the current truth of every module of :data:`SUBJECTS` not on file."""
    for subject in sorted(SUBJECTS):
        record(root, subject, at, backfill_all=True)


class WatchedStore(SubjectStore):
    """A subject store whose card commits re-check :data:`SUBJECTS`' modules."""

    def __init__(self, root: Path, clock: Callable[[], int]) -> None:
        """``clock`` is the context's, in ms."""
        super().__init__(root)
        self.clock = clock

    def commit(self, subject: str, meta: Meta, change: Change | None = None) -> Meta:
        """Commit, then record any flip the cards caused."""
        out = super().commit(subject, meta, change)
        if change is not None and subject in SUBJECTS:
            if change.cards is not None:
                record(self.root, subject, self.clock() / 1000)
            if change.cards is not None or change.plan is not None:
                review_due.record(self.root, subject, self.clock() / 1000)
        return out


class WatchedLog(EventLog):
    """An event log whose ``taught`` / ``untaught`` events re-check modules."""

    def __init__(self, root: Path, clock: Callable[[], int]) -> None:
        """``clock`` is the context's, in ms."""
        super().__init__(root)
        self.root = root
        self.clock = clock

    def append(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Store the new events, then record any flip they caused."""
        fresh = super().append(events)
        for subject in sorted({str(e["s"]) for e in fresh if "s" in e} & SUBJECTS):
            if any(e["k"] in _TEACHING and e["s"] == subject for e in fresh):
                record(self.root, subject, self.clock() / 1000)
            review_due.record(self.root, subject, self.clock() / 1000)  # C4
        return fresh
