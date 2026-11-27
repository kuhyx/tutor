# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Re-sign an untagged review row as a tagged twin of the same ``entry_id``.

A review minute written before rows named their module (contract C1) pays
minutes the LeetCode guard cannot count. Rows are never rewritten or removed,
so the fix is an appended twin: the same row, same ``entry_id``, minutes and
``ended_at``, whose signed ``detail`` also holds the :class:`~tutor.ledger_pay.Taught`
keys. Every reader of the ledger (earned_time, :func:`tutor.ledger_pay.paying`)
pays a repeated ``entry_id`` once, at its smallest count, and the twin repeats
the count, so what the tutor rung pays never changes.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Final

import earned_time

from tutor.ledger_io import (
    LedgerError,
    Paths,
    default_paths,
    exclusive,
    read_key,
    read_rows,
    write_rows,
)
from tutor.ledger_pay import CREDIT, Taught

# Which tags (if any) a verified untagged credit row, given its entry id and
# ``detail.ended_at``, should carry.
TagFor = Callable[[str, float], Taught | None]
REVIEW: Final = "review"
_logger = logging.getLogger(__name__)


def is_tagged(row: dict[str, Any]) -> bool:
    """Whether a row's ``detail`` already names a module and says it is a review."""
    detail = row.get("detail")
    return (
        isinstance(detail, dict)
        and "subject" in detail
        and "module" in detail
        and detail.get("activity") == REVIEW
    )


def twin_of(row: dict[str, Any], taught: Taught, key: bytes) -> dict[str, Any]:
    """``row`` signed again with ``taught`` added to its ``detail``."""
    body = {k: v for k, v in row.items() if k != "hmac"}
    body["detail"] = {**row["detail"], **{k: str(v) for k, v in taught.items()}}
    return {**body, "hmac": str(earned_time.entry_signature(body, key))}


def _twins(rows: list[object], tag_for: TagFor, key: bytes) -> list[dict[str, Any]]:
    """The twins ``rows`` still lack (one per ``entry_id``), oldest row first."""
    genuine = [
        r
        for r in rows
        if isinstance(r, dict)
        and r.get("kind") == CREDIT
        and isinstance(r.get("detail"), dict)
        and earned_time.verified(r, key)
    ]
    done = {r["entry_id"] for r in genuine if is_tagged(r)}
    fresh: list[dict[str, Any]] = []
    for row in genuine:
        entry, ended = row["entry_id"], row["detail"].get("ended_at")
        if (
            entry in done
            or isinstance(ended, bool)
            or not isinstance(ended, int | float)
        ):
            continue
        taught = tag_for(str(entry), float(ended))
        # A twin exists to name the module; one without it would never count
        # as tagged, so every later pass would append it again.
        if taught and "module" in taught:
            fresh.append(twin_of(row, taught, key))
            done.add(entry)
    return fresh


def backfill(tag_for: TagFor, *, paths: Paths | None = None) -> list[dict[str, Any]]:
    """Append the twins ``tag_for`` asks for, in one write; the twins written.

    Idempotent: an ``entry_id`` with a verified tagged row gets nothing. Only
    verified rows are re-signed. A failure is logged, never raised.
    """
    where = paths or default_paths()
    key = read_key(where.key_file)
    if key is None:
        return []
    try:
        with exclusive(where.lock):
            rows = read_rows(where.ledger)
            fresh = _twins(rows, tag_for, key)
            if fresh:
                write_rows(where.ledger, [*rows, *fresh])
    except (LedgerError, OSError) as exc:
        _logger.warning("review rows not re-signed with their module: %s", exc)
        return []
    return fresh
