# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Reading the Anki collection anki-guard's sync server holds open.

``anki --syncserver`` keeps the collection open (exclusive lock, WAL), so it
is never opened here: ``collection.anki2`` and its ``-wal`` are copied
together and the copy is read, where SQLite replays the WAL -- anki-guard's
proven ``_snapshot.py`` (not imported: it pins another earned-time, and its
modules are private). A copy is used only if neither file changed while
copying and it passes ``quick_check``. Retries are 50 ms apart, not
anki-guard's 2 s, so a torn copy still credits inside the ~1 s budget.

The review query is anki-guard ``_studied.py``'s minus the deck split: every
``revlog`` row except manual (4) and rescheduled (5) entries. ``time`` is in
milliseconds, already capped by the deck's "Maximum answer seconds".
"""

from __future__ import annotations

from contextlib import closing, contextmanager
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

COLLECTION_ENV: Final = "TUTOR_ANKI_COLLECTION"
ATTEMPTS: Final = 5
RETRY_S: Final = 0.05
_EXCLUDED_KINDS: Final = (4, 5)  # manual, rescheduled (anki-guard _studied.py)
_logger = logging.getLogger(__name__)

Fingerprint = tuple[tuple[int, int] | None, ...]


class AnkiError(Exception):
    """The collection is missing or could not be read consistently."""


def collection_path() -> Path:
    """The sync server's collection (``TUTOR_ANKI_COLLECTION`` overrides)."""
    override = os.environ.get(COLLECTION_ENV)
    if override:
        return Path(override)
    return Path.home() / ".local/share/anki_guard/syncserver/kuhy/collection.anki2"


def wal(path: Path) -> Path:
    """The collection's write-ahead log."""
    return path.with_name(path.name + "-wal")


def fingerprint(path: Path) -> Fingerprint:
    """(size, mtime_ns) of the database and its WAL; ``None`` if absent.

    Raises:
        FileNotFoundError: A file vanished between the check and the stat
            (a WAL checkpoint); :func:`snapshot` retries on it.
    """
    out: list[tuple[int, int] | None] = []
    for part in (path, wal(path)):
        if not part.exists():
            out.append(None)
            continue
        stat = part.stat()
        out.append((stat.st_size, stat.st_mtime_ns))
    return tuple(out)


def last_sync_at(path: Path) -> float | None:
    """Unix seconds the collection last changed (db or WAL), ``None`` if absent."""
    times = [entry[1] for entry in fingerprint(path) if entry is not None]
    return max(times) / 1e9 if times else None


def _unicase(left: str, right: str) -> int:
    """Anki's case-insensitive collation; quick_check needs it for its indexes."""
    a, b = left.casefold(), right.casefold()
    return (a > b) - (a < b)


def _connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.create_collation("unicase", _unicase)
    return db


def _copy_once(source: Path, target: Path) -> bool:
    """Copy db + WAL; usable only if neither changed and the copy checks ok."""
    before = fingerprint(source)
    if before[0] is None:
        msg = f"no Anki collection at {source} (has the phone synced yet?)"
        raise AnkiError(msg)
    wal(target).unlink(missing_ok=True)
    shutil.copyfile(source, target)
    if before[1] is not None:
        shutil.copyfile(wal(source), wal(target))
    if fingerprint(source) != before:
        return False
    try:
        with closing(_connect(target)) as db:
            row = db.execute("PRAGMA quick_check").fetchone()
    except sqlite3.DatabaseError as exc:
        _logger.warning("anki snapshot unreadable (%s); retrying", exc)
        return False
    return bool(row and row[0] == "ok")


@contextmanager
def snapshot(source: Path) -> Iterator[Path]:
    """A consistent private copy of ``source``, removed afterwards.

    Raises:
        AnkiError: No collection, an unreadable one, or every copy torn.
    """
    with tempfile.TemporaryDirectory(prefix="tutor-anki-") as tmp:
        target = Path(tmp) / "collection.anki2"
        for attempt in range(ATTEMPTS):
            try:
                if _copy_once(source, target):
                    break
            except FileNotFoundError as exc:  # a checkpoint took the WAL: retry
                _logger.warning("collection moved under the copy (%s); retrying", exc)
            except OSError as exc:
                msg = f"cannot copy {source}: {exc}"
                raise AnkiError(msg) from exc
            if attempt + 1 < ATTEMPTS:
                time.sleep(RETRY_S)
        else:
            msg = f"no consistent copy of {source} after {ATTEMPTS} attempts"
            raise AnkiError(msg)
        yield target


def reviews(copy: Path, since: float) -> list[tuple[int, int]]:
    """``(id ms, time ms)`` of the counted reviews from unix ``since`` on.

    Raises:
        AnkiError: ``copy`` has no readable ``revlog``.
    """
    try:
        with closing(_connect(copy)) as db:
            return db.execute(
                "SELECT id, time FROM revlog WHERE id >= ? AND type NOT IN (?, ?)"
                " ORDER BY id",
                (int(since * 1000), *_EXCLUDED_KINDS),
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        msg = f"{copy} is not a readable Anki collection: {exc}"
        raise AnkiError(msg) from exc
