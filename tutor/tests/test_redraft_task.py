# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The server's background card work: drain the redraft, then stale paths."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import cardgen, paths
from tutor.curriculum.errors import RequestError
from tutor.curriculum.redraft import run
from tutor.relay import redraft_task
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.redraft_task import CardWork, reply_in_flight
from tutor.tests._cur import card, module, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._redraft import URL, Fable, draft
from tutor.tests._relay_support import engine, wiring
from tutor.tests.test_paths import path

if TYPE_CHECKING:
    from pathlib import Path


def _work(tmp_path: Path) -> tuple[CardWork, Any]:
    eng, _ = engine(tmp_path)
    w = wiring(FakeRtdb(), eng)
    mods = [module("a", status="ready"), module("b", "a"), module("c", "b")]
    found = {"x": card("a", 1, source=URL), "y": card("a", 2, source=URL)}
    subject(eng.ctx, modules=mods, found=found)
    return CardWork(w, CurriculumSync(w), {"chat": None, "build": None}), eng


def test_a_pending_redraft_is_drained_then_paths_are_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, eng = _work(tmp_path)
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search")
    eng.fakes.texts[URL] = "the piston turns the crank shaft round and round " * 60
    eng.fakes.text = eng.fakes.text
    fable = Fable([draft("piston")], pairs=[("piston", "x")])
    monkeypatch.setattr(type(eng.fakes), "model", lambda _s, *a: fable(*a))

    async def go() -> list[str]:
        ctx = eng.ctx
        ctx.text = eng.fakes.text
        monkeypatch.setattr(type(eng), "ctx", property(lambda _e: ctx))
        run.start(ctx)
        first = await work.once()
        second = await work.once()  # x has its path from the redraft
        await work.w.rtdb.aclose()
        return [first, second]

    assert asyncio.run(go()) == ["redraft", "idle"]
    assert paths.fresh(eng.ctx, "car", "x") is not None
    assert eng.ctx.subjects.cards("car")["y"].suspended


def test_stale_paths_are_written_one_module_at_a_time(tmp_path: Path) -> None:
    work, eng = _work(tmp_path)
    eng.fakes.replies = [{"paths": [path("x"), path("y")]}]

    async def go() -> list[str]:
        out = [await work.once(), await work.once()]
        await work.w.rtdb.aclose()
        return out

    assert asyncio.run(go()) == ["paths", "idle"]
    assert paths.stale(eng.ctx, "car", "a") == []


def test_a_failed_path_write_is_not_retried_and_busy_waits(tmp_path: Path) -> None:
    work, eng = _work(tmp_path)
    eng.fakes.replies = [RequestError("model_error", "down")]

    async def go() -> list[str]:
        out = [await work.once(), await work.once()]
        work._failed.clear()
        work.current["chat"] = "rid"
        out.append(await work.once())
        await work.w.rtdb.aclose()
        return out

    assert asyncio.run(go()) == ["paths", "idle", "idle"]
    assert eng.fakes.replies == []


def test_reply_in_flight_reads_the_newest_transcript(tmp_path: Path) -> None:
    assert not reply_in_flight(tmp_path, 100.0)
    log = tmp_path / "20261121-1.jsonl"
    log.write_text(json.dumps({"type": "learner"}) + "\n")
    now = log.stat().st_mtime
    assert reply_in_flight(tmp_path, now)
    assert not reply_in_flight(tmp_path, now + redraft_task.FRESH_S + 1)
    log.write_text(json.dumps({"type": "tutor"}) + "\n")
    assert not reply_in_flight(tmp_path, now)
    log.write_text("not json\n")
    os.utime(log, (now, now))
    assert not reply_in_flight(tmp_path, now)
    log.write_text("")
    assert not reply_in_flight(tmp_path, log.stat().st_mtime)


def test_wait_blocks_while_busy_and_run_survives_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, _ = _work(tmp_path)
    work.current["chat"] = "rid"
    naps: list[float] = []

    def nap(seconds: float) -> None:
        naps.append(seconds)
        work.current["chat"] = None

    monkeypatch.setattr(time, "sleep", nap)
    work.wait()
    assert naps == [redraft_task.POLL_S]
    rounds: list[int] = []

    async def once() -> str:
        rounds.append(1)
        if len(rounds) == 1:
            msg = "boom"
            raise ValueError(msg)
        raise asyncio.CancelledError

    async def no_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr(work, "once", once)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(work.run())
    assert len(rounds) == 2
