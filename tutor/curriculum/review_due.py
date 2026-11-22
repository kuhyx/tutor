# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C4: a module's review queue as signed absolute due times.

leetcode-guard may only decide from signed tutor files, and the queue's due
dates come from the unsigned log fold. This file publishes them
(``DOCS-contract-review-due.md``): one row per (subject, module) listing the
``due`` (unix ms) of every card of the module that the queue holds (taught,
not flagged at its rev, not suspended; an archived subject holds none). A
reader counts the cards due at any later time T by comparing, without the
tutor running.

The envelope, signer, lock and atomic write are C2's (``module_state``). Unlike
C2 the writer keeps ONE row per (subject, module): it replaces the module's
row instead of appending, so the file stays the size of the plan however many
reviews follow. :func:`record` runs after every event or card commit of the
``module_state.SUBJECTS`` (``WatchedLog``, ``WatchedStore``) and at startup
(:func:`backfill`). A failed write logs a warning and never reaches the caller.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING, Any, Final

import earned_time

from tutor.curriculum.eventlog import EventLog, archived_subjects
from tutor.curriculum.fold import fold, without
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
    from collections.abc import Iterable
    from pathlib import Path

KIND: Final = "review_due"
VERSION: Final = 1
FILE: Final = "review_due.json"
LOCK: Final = "review_due.lock"
_logger = logging.getLogger(__name__)


def due_times(root: Path, subject: str) -> dict[str, list[int]]:
    """Plan module id -> sorted ``due`` (unix ms) of the queue's cards in it.

    The queue's own definition (``no_card.due_in_subject``, minus its "now"):
    taught, not flagged at the card's rev, not suspended. A module with no such
    card maps to ``[]``. Archiving masks the subject, as it does in the app.
    """
    store = SubjectStore(root)
    plan = store.plan(subject)
    out: dict[str, list[int]] = {m.id: [] for m in plan.modules} if plan else {}
    events = EventLog(root).read()
    folded = without(fold(events), archived_subjects(events))
    for cid, rec in store.cards(subject).items():
        if rec.suspended or rec.module not in out:
            continue
        state = folded.card(subject, cid)
        memory = state.fsrs_state()
        if memory is not None and not state.flagged(rec.rev):
            out[rec.module].append(memory["due"])
    return {module: sorted(due) for module, due in out.items()}


def _is_int(value: object) -> bool:
    """An int that is not a bool (JSON ``true`` is not a time)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _detail(row: dict[str, Any]) -> dict[str, Any] | None:
    """The row's ``detail`` if it is of this kind and has the contract's types."""
    detail = row.get("detail")
    if row.get("kind") != KIND or not isinstance(detail, dict):
        return None
    due, at = detail.get("due_ms"), detail.get("at")
    typed = (
        isinstance(detail.get("subject"), str)
        and isinstance(detail.get("module"), str)
        and isinstance(due, list)
        and all(_is_int(t) for t in due)
        and isinstance(at, int | float)
        and not isinstance(at, bool)
    )
    return detail if typed else None


def read_due(rows: list[object], key: bytes) -> dict[tuple[str, str], list[int]] | None:
    """(subject, module) -> due times, or ``None``: the file cannot be checked.

    Every entry must be a dict whose signature verifies; one that is not makes
    the whole file "cannot check" (it must not be skipped: skipping could hide
    the row that carries the due cards). A verified row that is not this kind
    or has no usable ``detail`` is skipped. Of several rows of one module the
    greatest ``at`` wins, a later one in the file on a tie.
    """
    best: dict[tuple[str, str], tuple[float, list[int]]] = {}
    for row in rows:
        if not isinstance(row, dict) or not earned_time.verified(row, key):
            return None
        detail = _detail(row)
        if detail is None:
            continue
        ref = (detail["subject"], detail["module"])
        if ref not in best or detail["at"] >= best[ref][0]:
            best[ref] = (detail["at"], detail["due_ms"])
    return {ref: due for ref, (_, due) in best.items()}


def count_due(
    path: Path, key: bytes, subject: str, module: str, at_ms: int
) -> int | None:
    """Cards of ``module`` due at ``at_ms`` (``due <= at_ms``), ``None`` if unknown.

    ``None``: no file, an unreadable file, a row that fails verification, or no
    row for the module ("cannot check"; never "nothing due").
    """
    try:
        rows = read_rows(path)
    except LedgerError as exc:
        _logger.warning("review due cannot be checked: %s", exc)
        return None
    due = read_due(rows, key)
    if due is None or (subject, module) not in due:
        return None
    return sum(t <= at_ms for t in due[subject, module])


def _prefix(row: object) -> str:
    """``due:<subject>:<module>:`` of a row's ``entry_id`` ("" if it has none)."""
    entry_id = str(row.get("entry_id", "")) if isinstance(row, dict) else ""
    return entry_id[: entry_id.rfind(":") + 1]


def _seq(row: object, prefix: str) -> int:
    """``n`` of the row's ``entry_id`` when it is of ``prefix``, else 0."""
    entry_id = str(row.get("entry_id", "")) if isinstance(row, dict) else ""
    num = entry_id[len(prefix) :]
    return int(num) if _prefix(row) == prefix and num.isdigit() else 0


def _row(prefix: str, n: int, detail: dict[str, Any], key: bytes) -> dict[str, Any]:
    """The signed row."""
    at = detail["at"]
    row: dict[str, Any] = {
        "kind": KIND,
        "entry_id": f"{prefix}{n}",
        "day": datetime.fromtimestamp(at, tz=UTC).astimezone().date().isoformat(),
        "detail": detail,
    }
    row["hmac"] = str(earned_time.entry_signature(row, key))
    return row


def reconcile(root: Path, subject: str, at: float) -> list[dict[str, Any]]:
    """Replace the row of each module whose due list differs from its row.

    A module with no verified row yet gets one, empty or not. Rows of other
    modules are kept as they are. Returns the rows written.

    Raises:
        LedgerError: ``review_due.json`` exists but is not a due file.
    """
    key = read_key(default_paths().key_file)
    if key is None:
        _logger.warning("review due of %s not recorded: no signing key", subject)
        return []
    path = root / FILE
    with exclusive(root / LOCK):
        rows = read_rows(path)
        known = read_due(rows, key) or {}
        fresh: list[dict[str, Any]] = []
        for module, due in due_times(root, subject).items():
            if known.get((subject, module)) == due:
                continue
            prefix = f"due:{subject}:{module}:"
            n = 1 + max((_seq(r, prefix) for r in rows), default=0)
            detail = {"subject": subject, "module": module, "due_ms": due, "at": at}
            fresh.append(_row(prefix, n, detail, key))
        if fresh:
            gone = {_prefix(r) for r in fresh}
            kept = [r for r in rows if _prefix(r) not in gone]
            write_rows(path, [*kept, *fresh], version=VERSION)
    return fresh


def record(root: Path, subject: str, at: float) -> None:
    """:func:`reconcile`, a failure logged at warning and swallowed."""
    try:
        reconcile(root, subject, at)
    except (OSError, ValueError, LedgerError) as exc:
        _logger.warning("review due of %s not recorded: %s", subject, exc)


def backfill(root: Path, at: float, subjects: Iterable[str]) -> None:
    """Write the current due list of every module of ``subjects`` at startup."""
    for subject in sorted(subjects):
        record(root, subject, at)
