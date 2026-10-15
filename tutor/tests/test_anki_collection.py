# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Snapshot copies of the sync server's collection and the review query."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

import pytest

from tutor import anki_collection as col
from tutor.tests._anki_support import make_collection

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(col, "RETRY_S", 0.0)


def test_collection_path_defaults_under_home_and_honours_the_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(col.COLLECTION_ENV, raising=False)
    assert col.collection_path() == (
        tmp_path / "home/.local/share/anki_guard/syncserver/kuhy/collection.anki2"
    )
    monkeypatch.setenv(col.COLLECTION_ENV, str(tmp_path / "x.anki2"))
    assert col.collection_path() == tmp_path / "x.anki2"


def test_fingerprint_and_last_sync_follow_the_newest_file(tmp_path: Path) -> None:
    path = tmp_path / "c.anki2"
    assert col.fingerprint(path) == (None, None)
    assert col.last_sync_at(path) is None
    make_collection(path, [(1_000, 5_000, 1)], keep_wal=True)
    os.utime(path, (100, 100))
    os.utime(col.wal(path), (200, 200))
    assert col.last_sync_at(path) == 200.0


def test_snapshot_reads_rows_still_in_the_wal(tmp_path: Path) -> None:
    path = tmp_path / "c.anki2"
    make_collection(path, [(1_000, 5_000, 1), (2_000, 7_000, 4)], keep_wal=True)
    with col.snapshot(path) as copy:
        assert copy != path
        assert col.reviews(copy, 0) == [(1_000, 5_000)]  # type 4 excluded
        assert col.reviews(copy, 1.5) == []
    assert not copy.exists()


def test_snapshot_without_a_wal(tmp_path: Path) -> None:
    path = tmp_path / "c.anki2"
    make_collection(path, [(3_000, 1, 0)], keep_wal=False)
    with col.snapshot(path) as copy:
        assert col.reviews(copy, 0) == [(3_000, 1)]


def test_missing_collection_is_an_error(tmp_path: Path) -> None:
    with (
        pytest.raises(col.AnkiError, match="no Anki collection"),
        col.snapshot(tmp_path / "none.anki2"),
    ):
        pass


def test_a_copy_that_never_settles_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.anki2"
    make_collection(path, [], keep_wal=True)
    ticks = iter(range(100))
    real = col.fingerprint

    def moving(source: Path) -> col.Fingerprint:
        return (*real(source), (next(ticks), 0))

    monkeypatch.setattr(col, "fingerprint", moving)
    with pytest.raises(col.AnkiError, match="no consistent copy"), col.snapshot(path):
        pass


def test_a_checkpoint_racing_the_copy_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.anki2"
    make_collection(path, [(1_000, 2, 1)], keep_wal=True)
    calls = {"n": 0}
    real = shutil.copyfile

    def flaky(src: Path, dst: Path) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            raise FileNotFoundError(src)
        return real(src, dst)

    monkeypatch.setattr(shutil, "copyfile", flaky)
    with col.snapshot(path) as copy:
        assert col.reviews(copy, 0) == [(1_000, 2)]


def test_an_uncopyable_collection_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.anki2"
    make_collection(path, [], keep_wal=False)

    def denied(src: Path, _dst: Path) -> object:
        raise PermissionError(src)

    monkeypatch.setattr(shutil, "copyfile", denied)
    with pytest.raises(col.AnkiError, match="cannot copy"), col.snapshot(path):
        pass


def test_a_file_that_is_not_sqlite_never_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "c.anki2"
    path.write_bytes(b"not a database at all" * 300)
    with pytest.raises(col.AnkiError, match="no consistent copy"), col.snapshot(path):
        pass


def test_a_database_without_a_revlog_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "other.db"
    path.touch()
    with pytest.raises(col.AnkiError, match="not a readable Anki collection"):
        col.reviews(path, 0)


def test_unicase_is_a_case_insensitive_order() -> None:
    assert col._unicase("Deck", "deck") == 0
    assert col._unicase("a", "B") == -1
    assert col._unicase("b", "A") == 1
