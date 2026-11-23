# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Signed files of the post-mortem: rows in an envelope, or one signed document.

The signer is the fleet's (``earned_time.entry_signature``, the key of
``ledger_io.default_paths``), the same one ``module_state`` and C3 use, so
leetcode-guard verifies these rows with ``gatelock.log_integrity``.

"Cannot read" is not "empty": :func:`verified_rows` answers ``None`` for a
missing key or a broken file, and drops (logged) a row whose signature fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from typing import TYPE_CHECKING, Any, Final

import earned_time

from tutor.ledger_io import (
    LedgerError,
    default_paths,
    exclusive,
    read_key,
    read_rows,
    write_rows,
)

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)
VERSION: Final = 1
type Row = dict[str, Any]


def key() -> bytes | None:
    """The signing key, or ``None`` (logged by ``read_key``)."""
    return read_key(default_paths().key_file)


def local_day(at: float) -> str:
    """The PC-local date of unix seconds ``at``."""
    return datetime.fromtimestamp(at, tz=UTC).astimezone().date().isoformat()


def signed(row: Row, secret: bytes) -> Row:
    """``row`` with its ``hmac`` (any old one replaced)."""
    body = {k: v for k, v in row.items() if k != "hmac"}
    return {**body, "hmac": str(earned_time.entry_signature(body, secret))}


def valid(row: object, secret: bytes) -> bool:
    """Whether ``row`` is a dict whose signature verifies; a raising check fails."""
    if not isinstance(row, dict):
        return False
    try:
        return bool(earned_time.verified(row, secret))
    except (TypeError, ValueError) as err:  # a non-ASCII hmac: compare_digest raises
        _logger.warning("post-mortem: a row's signature check raised: %s", err)
        return False


def verified_rows(path: Path, kind: str) -> list[Row] | None:
    """The verified ``kind`` rows of the envelope at ``path``; ``None``: cannot read.

    A missing file is no rows. A row whose signature fails is dropped, once logged.
    """
    secret = key()
    if secret is None:
        return None
    try:
        rows = read_rows(path)
    except LedgerError as err:
        _logger.warning("post-mortem: %s", err)
        return None
    kept = [r for r in rows if valid(r, secret)]
    if len(kept) != len(rows):
        _logger.warning("%s: %d unverified rows ignored", path, len(rows) - len(kept))
    return [r for r in kept if isinstance(r, dict) and r.get("kind") == kind]


def append_row(path: Path, row: Row) -> Row | None:
    """Sign ``row`` and append it under the file's lock; ``None``: not written."""
    secret = key()
    if secret is None:
        _logger.warning("post-mortem: no signing key, %s not written", path)
        return None
    made = signed(row, secret)
    with exclusive(path.with_suffix(".lock")):
        try:
            rows = read_rows(path)
        except LedgerError as err:
            _logger.warning("post-mortem: %s, row not written", err)
            return None
        write_rows(path, [*rows, made], version=VERSION)
    return made


def write_doc(path: Path, doc: Row) -> bool:
    """Write ``doc`` signed as one row (atomically); ``False``: not written."""
    secret = key()
    if secret is None:
        _logger.warning("post-mortem: no signing key, %s not written", path)
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(signed(doc, secret), indent=1), encoding="utf-8")
    tmp.replace(path)
    return True


def read_doc(path: Path) -> Row | None:
    """The signed document at ``path``; ``None`` when missing, broken or forged."""
    secret = key()
    if secret is None or not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        _logger.warning("post-mortem: %s unreadable: %s", path, err)
        return None
    if not valid(doc, secret):
        _logger.warning("post-mortem: %s fails its signature, ignored", path)
        return None
    return dict(doc)
