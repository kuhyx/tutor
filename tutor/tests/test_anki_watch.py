# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The inotify watcher that credits Anki reviews as a sync lands."""

from __future__ import annotations

import asyncio
import ctypes
import errno
import logging
import shutil
from typing import TYPE_CHECKING

import pytest

from tutor import anki, anki_collection, anki_watch

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class _NoInotify:
    """A libc without inotify."""


class _FailingInit:
    """A libc whose inotify_init1 fails."""

    @staticmethod
    def inotify_init1(_flags: int) -> int:
        return -1

    @staticmethod
    def inotify_add_watch(_fd: int, _path: bytes, _mask: int) -> int:
        return 0


async def _until(check: Callable[[], bool], limit: float = 3.0) -> None:
    waited = 0.0
    while not check():
        assert waited < limit, "condition never held"
        await asyncio.sleep(0.005)
        waited += 0.005


def test_inotify_reports_names_and_a_deleted_directory(tmp_path: Path) -> None:
    watched = tmp_path / "sync"
    watched.mkdir()
    notify = anki_watch.Inotify(watched)
    try:
        assert notify.read() == (set(), False)
        (watched / "collection.anki2-wal").write_bytes(b"x")
        assert notify.read() == ({"collection.anki2-wal"}, False)
        shutil.rmtree(watched)
        names, gone = notify.read()
        assert gone
        assert "collection.anki2-wal" in names
    finally:
        notify.close()


def test_inotify_errors_are_oserrors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(FileNotFoundError):
        anki_watch.Inotify(tmp_path / "missing")
    monkeypatch.setattr(ctypes, "CDLL", lambda *_a, **_k: _FailingInit())
    monkeypatch.setattr(ctypes, "get_errno", lambda: errno.EMFILE)
    with pytest.raises(OSError, match="Too many open files"):
        anki_watch.Inotify(tmp_path)
    monkeypatch.setattr(ctypes, "CDLL", lambda *_a, **_k: _NoInotify())
    with pytest.raises(OSError, match="no inotify"):
        anki_watch.Inotify(tmp_path)


def test_writes_to_the_collection_trigger_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def body() -> None:
        monkeypatch.setattr(anki_watch, "DEBOUNCE_S", 0.01)
        monkeypatch.setattr(anki_watch, "MAX_WAIT_S", 0.05)
        target = tmp_path / "sync/collection.anki2"
        target.parent.mkdir()
        passes: list[int] = []
        task = asyncio.create_task(anki_watch.watch(target, lambda: passes.append(1)))
        try:
            await _until(lambda: len(passes) == 1)  # the pass on arming
            await asyncio.sleep(0.05)
            (target.parent / "media.db").write_bytes(b"x")  # not the collection
            await asyncio.sleep(0.1)
            assert len(passes) == 1
            target.write_bytes(b"x")
            await _until(lambda: len(passes) == 2)
            for _ in range(40):  # a long sync: the debounce gives up waiting
                with target.open("ab") as out:
                    out.write(b"y")
                await asyncio.sleep(0.003)
            await _until(lambda: len(passes) >= 4)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(body())


def test_a_lost_directory_falls_back_to_polling_then_rearms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def body() -> None:
        monkeypatch.setattr(anki_watch, "POLL_S", 0.01)
        monkeypatch.setattr(anki_watch, "REARM_S", 0.05)
        target = tmp_path / "sync/collection.anki2"
        target.parent.mkdir()
        passes: list[int] = []
        task = asyncio.create_task(anki_watch.watch(target, lambda: passes.append(1)))
        try:
            await _until(lambda: len(passes) == 1)
            with caplog.at_level(logging.WARNING):
                shutil.rmtree(target.parent)
                await asyncio.sleep(0.2)  # several failed re-arms, logged once
                assert caplog.text.count("cannot watch") == 1
                assert len(passes) == 1
                target.parent.mkdir()  # the poll sees the collection appear
                target.write_bytes(b"x")
                await _until(lambda: len(passes) >= 3)  # poll pass + arming pass
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(body())


def test_the_default_pass_credits_the_watched_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def body() -> None:
        target = tmp_path / "collection.anki2"
        seen: list[object] = []

        def fake_credit_now(
            now: float | None = None, source: Path | None = None
        ) -> None:
            seen.append((now, source))

        monkeypatch.setattr(anki, "credit_now", fake_credit_now)
        task = asyncio.create_task(anki_watch.watch(target))
        try:
            await _until(lambda: bool(seen))
            assert seen[0] == (None, target)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(body())


def test_a_stat_racing_a_checkpoint_reads_as_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def vanished(path: Path) -> anki_collection.Fingerprint:
        raise FileNotFoundError(path)

    monkeypatch.setattr(anki_collection, "fingerprint", vanished)
    with caplog.at_level(logging.WARNING):
        assert anki_watch._stat(tmp_path / "c.anki2") == ()
    assert "changed under the stat" in caplog.text
