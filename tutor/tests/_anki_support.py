# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A tiny synthetic Anki collection: the tables the Anki credit reads."""

from __future__ import annotations

from contextlib import closing
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# (revlog id = unix ms, time ms, type)
Review = tuple[int, int, int]
TUTOR_CARD, LC_CARD, LC_SUB_CARD = 1, 2, 3  # in Default, LeetCode, LeetCode::Sub


def make_collection(path: Path, reviews: list[Review], *, keep_wal: bool) -> None:
    """Write ``path`` in WAL mode; ``keep_wal`` leaves rows in an un-checkpointed WAL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=wal")
    db.execute(
        "CREATE TABLE revlog (id INTEGER PRIMARY KEY, cid INTEGER, usn INTEGER,"
        " ease INTEGER, ivl INTEGER, lastIvl INTEGER, factor INTEGER,"
        " time INTEGER, type INTEGER)"
    )
    db.execute("CREATE TABLE col (mod INTEGER)")
    db.execute("INSERT INTO col VALUES (0)")
    db.execute("CREATE TABLE decks (id INTEGER PRIMARY KEY, name TEXT)")
    db.executemany(
        "INSERT INTO decks VALUES (?, ?)",
        [(1, "Default"), (2, "LeetCode"), (3, "LeetCode\x1fSub"), (4, "LeetCodeX")],
    )
    db.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY, did INTEGER)")
    db.executemany("INSERT INTO cards VALUES (?, ?)", [(1, 1), (2, 2), (3, 3), (4, 4)])
    add(db, reviews)
    # keep_wal: no closing checkpoint, as the sync server's open handle leaves it
    db.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, keep_wal)
    db.close()


def add(db: sqlite3.Connection, reviews: list[Review], card: int = TUTOR_CARD) -> None:
    """Append ``reviews`` of ``card`` and commit."""
    db.executemany(
        "INSERT INTO revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type)"
        " VALUES (?, ?, -1, 3, 1, 0, 2500, ?, ?)",
        [(rid, card, ms, kind) for rid, ms, kind in reviews],
    )
    db.commit()


def append(path: Path, reviews: list[Review], card: int = TUTOR_CARD) -> None:
    """Add ``reviews`` of ``card`` to an existing collection, keeping its WAL."""
    with closing(sqlite3.connect(path)) as db:
        db.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
        add(db, reviews, card)
