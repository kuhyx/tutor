# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Credit Anki reviews the moment an AnkiDroid sync lands on the collection.

inotify, through ctypes on libc (no dependency), on the collection's
DIRECTORY, not its files: a checkpoint deletes and recreates the WAL and a
full sync replaces the database. A write to ``collection.anki2`` or its
``-wal`` starts a trailing debounce (:data:`DEBOUNCE_S` of quiet, at most
:data:`MAX_WAIT_S`), then one credit pass in a worker thread. Idle cost: one
fd, no wakeups. A pass also runs whenever the watch starts, for syncs that
landed while the server was down.

Where inotify cannot watch (no directory yet, no inotify, the watch limit),
a stat poll every :data:`POLL_S` (two ``stat`` calls) stands in for
:data:`REARM_S`, then inotify is tried again. Nothing here raises into the
server: :func:`tutor.anki.credit_now` logs a missing or unreadable collection.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import select
import struct
from typing import TYPE_CHECKING, Final

from tutor import anki, anki_collection

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

DEBOUNCE_S: Final = 0.02
MAX_WAIT_S: Final = 0.5
POLL_S: Final = 0.2
REARM_S: Final = 30.0
NAMES: Final = frozenset({"collection.anki2", "collection.anki2-wal"})
# <sys/inotify.h>
_IN_MODIFY: Final = 0x2
_IN_CLOSE_WRITE: Final = 0x8
_IN_MOVED_TO: Final = 0x80
_IN_CREATE: Final = 0x100
_IN_DELETE: Final = 0x200
_IN_DELETE_SELF: Final = 0x400
_IN_MOVE_SELF: Final = 0x800
_IN_IGNORED: Final = 0x8000
_MASK: Final = (
    _IN_MODIFY
    | _IN_CLOSE_WRITE
    | _IN_MOVED_TO
    | _IN_CREATE
    | _IN_DELETE
    | _IN_DELETE_SELF
    | _IN_MOVE_SELF
)
_GONE: Final = _IN_DELETE_SELF | _IN_MOVE_SELF | _IN_IGNORED
_EVENT: Final = struct.Struct("iIII")  # wd, mask, cookie, len; then the name
_READ_BYTES: Final = 64 * 1024
_logger = logging.getLogger(__name__)


def _errno_error() -> OSError:
    number = ctypes.get_errno()
    return OSError(number, os.strerror(number))


class Inotify:
    """One non-blocking inotify watch on a directory.

    Raises:
        OSError: inotify is unavailable or the directory cannot be watched.
    """

    def __init__(self, directory: Path) -> None:
        """Open the fd and add the watch."""
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            init, add = libc.inotify_init1, libc.inotify_add_watch
        except AttributeError as exc:
            msg = "this libc has no inotify"
            raise OSError(msg) from exc
        fd = int(init(os.O_NONBLOCK | os.O_CLOEXEC))
        if fd < 0:
            raise _errno_error()
        if int(add(fd, os.fsencode(directory), _MASK)) < 0:
            error = _errno_error()
            os.close(fd)
            raise error
        self.fd = fd

    def read(self) -> tuple[set[str], bool]:
        """Names touched since the last read, and whether the watch is gone."""
        names: set[str] = set()
        gone = False
        while select.select([self.fd], [], [], 0)[0]:
            buf = os.read(self.fd, _READ_BYTES)
            offset = 0
            while offset < len(buf):
                _, mask, _, size = _EVENT.unpack_from(buf, offset)
                start = offset + _EVENT.size
                name = buf[start : start + size].rstrip(b"\0")
                names.add(name.decode(errors="replace"))
                gone = gone or bool(mask & _GONE)
                offset = start + size
        return names, gone

    def close(self) -> None:
        """Release the fd (and with it the watch)."""
        os.close(self.fd)


async def _pass(run: Callable[[], object]) -> None:
    """One credit pass off the event loop (sqlite, file copies, ledger lock)."""
    await asyncio.to_thread(run)


def _take(notify: Inotify, ready: asyncio.Event) -> tuple[bool, bool]:
    """Drain the fd: (did the collection change, is the watch gone)."""
    ready.clear()
    names, gone = notify.read()
    return bool(names & NAMES), gone


async def _serve(notify: Inotify, run: Callable[[], object]) -> None:
    """Credit on every collection write until the watch is gone."""
    loop = asyncio.get_running_loop()
    ready = asyncio.Event()
    loop.add_reader(notify.fd, ready.set)
    try:
        await _pass(run)
        gone = False
        while not gone:
            await ready.wait()
            changed, gone = _take(notify, ready)
            waited = 0.0
            while changed and waited < MAX_WAIT_S:  # trailing debounce
                await asyncio.sleep(DEBOUNCE_S)
                waited += DEBOUNCE_S
                if not ready.is_set():
                    break
                gone = _take(notify, ready)[1] or gone
            if changed:
                await _pass(run)
    finally:
        loop.remove_reader(notify.fd)


def _stat(target: Path) -> anki_collection.Fingerprint:
    """The collection's fingerprint; ``()`` (a change) if a file raced away."""
    try:
        return anki_collection.fingerprint(target)
    except FileNotFoundError as exc:
        _logger.warning("anki: %s changed under the stat (%s)", target, exc)
        return ()


async def _poll(target: Path, run: Callable[[], object], span: float) -> None:
    """For ``span`` s, credit whenever the collection's stat changes."""
    seen = _stat(target)
    for _ in range(round(span / POLL_S)):
        await asyncio.sleep(POLL_S)
        now = _stat(target)
        if now != seen:
            seen = now
            await _pass(run)


async def watch(
    source: Path | None = None, run: Callable[[], object] | None = None
) -> None:
    """Credit Anki reviews on every collection change, until cancelled."""
    target = source or anki_collection.collection_path()
    credit = run or (lambda: anki.credit_now(source=target))
    last_error = ""
    while True:
        try:
            notify = Inotify(target.parent)
        except OSError as exc:
            if str(exc) != last_error:
                _logger.warning("anki: cannot watch %s (%s); polling", target, exc)
                last_error = str(exc)
            await _poll(target, credit, REARM_S)
            continue
        last_error = ""
        try:
            await _serve(notify, credit)
        finally:
            notify.close()
