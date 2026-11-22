# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The review watcher: PC-clock delays from a stream arrival to ``log.jsonl``."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import review_due_watch as watch_mod
from tutor.relay import config, sse
from tutor.relay.sse import Event

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

OWN = "own-dev"
PHONE = "phone-dev"


@pytest.mark.parametrize(
    ("event", "want"),
    [
        (Event("put", "/", {PHONE: {"e0": {}}}), []),  # the dump on connect
        (Event("put", f"/{PHONE}/e1", {"k": "review"}), [(PHONE, "e1")]),
        (Event("put", f"/{PHONE}/e1/r", 3), [(PHONE, "e1")]),
        (
            Event("patch", f"/{PHONE}", {"e2": {}, "e3": {}}),
            [(PHONE, "e2"), (PHONE, "e3")],
        ),
        (Event("patch", f"/{OWN}", {"e4": {}}), []),
        (
            Event(
                "patch", "/", {f"{PHONE}/e5": {}, f"{OWN}/e6": {}, PHONE: {"e7": {}}}
            ),
            [(PHONE, "e5"), (PHONE, "e7")],
        ),
        (Event("patch", "/", {"junk": 1}), []),
        (Event("put", f"/{PHONE}", None), []),
    ],
)
def test_foreign_eids(event: Event, want: list[tuple[str, str]]) -> None:
    assert watch_mod.foreign_eids(event, OWN) == want


def tracker(tmp_path: Path) -> watch_mod.Tracker:
    data = tmp_path / "data"
    data.mkdir()
    return watch_mod.Tracker(
        OWN, data / "log.jsonl", data / "review_due.json", tmp_path / "out.jsonl"
    )


def test_poll_reports_a_landed_eid_and_a_moved_due_file(tmp_path: Path) -> None:
    track = tracker(tmp_path)
    assert track.poll(1.0) == []  # nothing pending, no files
    track.arrived([(PHONE, "e1"), (PHONE, "e2")], 10.0)
    assert track.poll(10.5) == []  # no log.jsonl yet
    track.log.write_text('{"eid": "e1"}\n')
    track.due.write_text("{}")
    rows = track.poll(11.25)
    assert rows[0]["kind"] == "review_due"
    assert rows[1] == {
        "kind": "landed",
        "eid": "e1",
        "dev": PHONE,
        "arrived": 10.0,
        "landed": 11.25,
        "delay_s": 1.25,
    }
    assert track.poll(12.0) == []  # same mtime: not read again
    assert list(track.pending) == ["e2"]


def test_watch_writes_rows_until_its_time_is_up(tmp_path: Path) -> None:
    track = tracker(tmp_path)
    now = [100.0]

    async def events() -> AsyncIterator[Event]:
        yield Event("put", f"/{PHONE}/e1", {})
        track.log.write_text('{"eid": "e1"}\n')
        await asyncio.Event().wait()  # the stream stays open

    async def sleep(seconds: float) -> None:
        now[0] += seconds
        await asyncio.sleep(0)

    asyncio.run(
        watch_mod.watch(events(), track, clock=lambda: now[0], sleep=sleep, run_s=1)
    )
    rows = [json.loads(line) for line in track.out.read_text().splitlines()]
    assert [r["eid"] for r in rows] == ["e1"]


def test_watch_ends_when_the_stream_does(tmp_path: Path) -> None:
    async def events() -> AsyncIterator[Event]:
        return
        yield  # makes this an async generator

    asyncio.run(watch_mod.watch(events(), tracker(tmp_path), run_s=60))
    assert not (tmp_path / "out.jsonl").exists()


def test_main_watches_the_data_dir_with_the_worker_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "share"
    data.mkdir()
    (data / "device_id").write_text(OWN)
    monkeypatch.setenv("TUTOR_DATA", str(data))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    seen: dict[str, Any] = {}

    class Rtdb:
        closed = False

        async def aclose(self) -> None:
            self.closed = True

    rtdb = Rtdb()

    async def connect() -> Rtdb:
        return rtdb

    async def fake_watch(events: object, track: watch_mod.Tracker, **kw: float) -> None:
        seen.update(events=events, track=track, kw=kw)

    monkeypatch.setattr(config, "connect_sealed", connect)
    monkeypatch.setattr(sse, "listen", lambda db, path: (db, path))
    monkeypatch.setattr(watch_mod, "watch", fake_watch)
    assert watch_mod.main() == 0
    assert seen["events"] == (rtdb, "log")
    assert seen["track"].own == OWN
    assert seen["track"].log == data / "log.jsonl"
    assert seen["track"].out == tmp_path / "state" / "tutor" / "review_due_watch.jsonl"
    assert seen["kw"] == {"run_s": watch_mod.RUN_S}
    assert rtdb.closed


def test_out_path_defaults_to_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert (
        watch_mod.out_path() == tmp_path / ".local/state/tutor/review_due_watch.jsonl"
    )
