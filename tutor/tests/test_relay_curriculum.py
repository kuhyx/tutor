# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The curriculum over RTDB: log both ways, subjects published, generation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tutor.curriculum import handlers as cur
from tutor.curriculum.eventlog import worker_event
from tutor.relay import cli
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.tests._cur import card, module, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import PHONE, WORKER, engine, wiring
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.curriculum.context import Context
    from tutor.engine import Engine

T = 1_800_000_000_000
EID = "01M4RBCX52MMHCK7K73E6KV910"
EID2 = "01M4RBCX52MMHCK7K73E6KV911"


def review(eid: str) -> dict[str, Any]:
    return {"k": "review", "s": "car", "c": "a-1", "r": 3, "at": T, "rev": 1}


def rig(tmp_path: Path) -> tuple[Engine, FakeRtdb, CurriculumSync]:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    return eng, fake, CurriculumSync(wiring(fake, eng))


def test_pull_mirrors_other_devices_incrementally(tmp_path: Path) -> None:
    eng, fake, sync = rig(tmp_path)
    fake.set(f"tutor/v1/log/{PHONE}/{EID}", review(EID))
    fake.set(f"tutor/v1/log/{WORKER}/{EID}", review(EID))  # our own: skipped
    fake.set(f"tutor/v1/log/not-a-device/{EID}", review(EID))
    fake.set("tutor/v1/log/" + WORKER.replace("1", "2"), "junk")  # not an object

    async def go() -> None:
        assert await sync.pull() == 1
        fake.set(f"tutor/v1/log/{PHONE}/{EID2}", review(EID2))
        fake.log.clear()
        assert await sync.pull() == 1
        assert ("GET", f"/log/{PHONE}") in fake.log
        assert await sync.pull() == 0  # startAt re-reads the newest only
        fake.set("tutor/v1/log", None)
        assert await sync.pull() == 0
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    assert [e["dev"] for e in eng.ctx.log.read()] == [PHONE, PHONE]


def test_push_sends_own_events_once(tmp_path: Path) -> None:
    eng, fake, sync = rig(tmp_path)
    own = worker_event("taught", ("car", "a-1"), dev=WORKER, at=T, session="s")
    eng.ctx.log.append([own, {**own, "dev": PHONE, "eid": EID}])

    async def go() -> None:
        await sync.push()
        fake.log.clear()
        await sync.push()
        assert fake.log == []
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    node = fake.get(f"tutor/v1/log/{WORKER}/{own['eid']}")
    assert node == {k: v for k, v in own.items() if k not in {"dev", "eid"}}
    assert fake.get(f"tutor/v1/log/{PHONE}") is None


def test_publish_only_moved_parts(tmp_path: Path) -> None:
    eng, fake, sync = rig(tmp_path)
    subject(eng.ctx, "car")

    async def go() -> None:
        assert await sync.publish("car")
        assert not await sync.publish("car")  # rev unchanged
        ctx = eng.ctx
        meta = ctx.subjects.need_meta("car")
        ctx.subjects.commit("car", meta)  # rev + 1, nothing else
        fake.log.clear()
        assert await sync.publish("car")
        assert [p for _, p in fake.log] == ["/subjects/car/meta"]
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    assert fake.get("tutor/v1/subjects/car/plan/status") == "approved"
    assert fake.get("tutor/v1/subjects/car/meta/rev") == 2


def test_startup_and_sync_queue_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    eng, fake, sync = rig(tmp_path)
    subject(eng.ctx, "car")
    subject(eng.ctx, "bike")
    fake.set("tutor/v1/subjects/bike/meta/rev", 1)  # already published
    fake.set("tutor/v1/rev/catalog", 7)
    fake.set(f"tutor/v1/log/{WORKER}/{EID}", review(EID))
    made: list[tuple[str, str]] = []

    def fold(_ctx: Context) -> dict[str, Any]:
        return {"changed": [], "generate": [["car", "b"], ["car", "c"]]}

    def generate(_ctx: Context, subj: str, module: str) -> dict[str, Any]:
        made.append((subj, module))
        if module == "c":
            msg = "model down"
            raise RuntimeError(msg)
        return {}

    monkeypatch.setattr(cur, "fold_and_advance", fold)
    monkeypatch.setattr(cur, "generate", generate)

    async def go() -> None:
        await sync.startup()
        assert fake.get("tutor/v1/rev/catalog") == 8
        assert fake.get("tutor/v1/subjects/bike") == {"meta": {"rev": 1}}
        await sync.sync()  # already queued: not twice
        task = asyncio.create_task(sync.generate_forever())
        for _ in range(100):
            await asyncio.sleep(0.01)
            if len(made) == 2 and sync.queue.empty():
                break
        await asyncio.sleep(0.02)
        task.cancel()
        await sync.sync()
        assert sync.queue.qsize() == 1  # b again (still pending); c failed: never
        await sync.w.rtdb.aclose()

    with caplog.at_level(logging.WARNING):
        asyncio.run(go())
    assert made[:2] == [("car", "b"), ("car", "c")]
    assert "generating car/c failed: model down" in caplog.text


def test_a_phone_review_unlocks_the_next_module_on_the_next_sync(
    tmp_path: Path,
) -> None:
    """A review synced from the app is enough: no other event is needed.

    ``sync`` runs every minute (``Relay._refresh``) and around each request.
    """
    eng, fake, sync = rig(tmp_path)
    found = {"a-1": card("a", 1), "b-1": card("b", 1)}
    mods = [module("a", status="ready"), module("b", "a", pregenerated=True)]
    subject(eng.ctx, "car", modules=mods, found=found)
    own = worker_event("taught", ("car", "a-1"), dev=WORKER, at=T, session="s")
    eng.ctx.log.append([own])

    async def go() -> None:
        await sync.startup()
        assert fake.get("tutor/v1/subjects/car/plan/modules")[1]["status"] == "locked"
        catalog = fake.get("tutor/v1/rev/catalog")
        fake.set(f"tutor/v1/log/{PHONE}/{EID}", {**review(EID), "at": T + 60_000})
        await sync.sync()
        assert fake.get("tutor/v1/rev/catalog") == catalog + 1
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    statuses = [m["status"] for m in fake.get("tutor/v1/subjects/car/plan/modules")]
    assert statuses == ["mastered", "ready"]


def test_publish_subjects_for_the_migration(tmp_path: Path) -> None:
    eng, fake, sync = rig(tmp_path)
    subject(eng.ctx, "car")
    own = worker_event("taught", ("car", "a-1"), dev=WORKER, at=T)
    eng.ctx.log.append([own])

    async def go() -> int:
        try:
            return await cli.publish_subjects(sync)
        finally:
            await sync.w.rtdb.aclose()

    assert asyncio.run(go()) == 1
    assert fake.get(f"tutor/v1/log/{WORKER}/{own['eid']}/k") == "taught"


def test_a_broken_fold_never_fails_chat_requests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Q2?"))

    def broken(_ctx: Context) -> dict[str, Any]:
        msg = "bad subject file"
        raise ValueError(msg)

    monkeypatch.setattr(cur, "fold_and_advance", broken)

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": None, "card": None})
        sid = got["data"]["session"]
        got = await rig.send("message", {"session": sid, "text": "an answer"})
        assert got["ok"]

    with caplog.at_level(logging.WARNING):
        run(eng, script)
    assert "curriculum sync failed: bad subject file" in caplog.text
