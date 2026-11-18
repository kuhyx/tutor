# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``subject_archive`` / ``subject_unarchive`` over the relay: catalog and log."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import archive
from tutor.curriculum import handlers as cur
from tutor.relay import protocol
from tutor.relay.cli import publish_subjects
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.errors import RequestError
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, WORKER, engine, wiring
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

ROOT = "tutor/v1-e2e"
PICK = f"{ROOT}/prefs/current_subject"


def _car(root: Path) -> None:
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(3)}
    subject(ctx, modules=[module("a", status="ready")], found=found)


@pytest.mark.parametrize("kind", ["subject_archive", "subject_unarchive"])
def test_protocol_puts_both_kinds_on_the_build_lane(kind: str) -> None:
    raw = {"kind": kind, "dev": WORKER, "created": 1, "body": {"subject": "car"}}
    got = protocol.validate(RIDS[0], raw)
    assert (got.lane, got.body) == (protocol.BUILD, {"subject": "car"})
    with pytest.raises(RequestError):
        protocol.validate(RIDS[0], {**raw, "body": {"subject": "Not A Slug"}})


def test_archive_removes_the_subject_and_undo_republishes_it(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    _car(tmp_path / "data")

    async def script(rig: Rig) -> None:
        await rig.server.sync()  # the first sync publishes car
        whole = rig.fake.get(f"{ROOT}/subjects/car")
        assert {"meta", "plan", "cards"} <= set(whole)
        catalog = rig.fake.get(f"{ROOT}/rev/catalog")
        got = await rig.send("subject_archive", {"subject": "car"})
        assert got["ok"], got
        assert got["data"] == {"subject": "car", "archived": True}
        assert rig.fake.get(f"{ROOT}/subjects/car") is None
        assert rig.fake.get(f"{ROOT}/rev/catalog") == catalog + 1
        own = rig.fake.get(f"{ROOT}/log/{WORKER}")
        assert [e["k"] for e in own.values()] == ["subject_archive"]
        got = await rig.send("subject_unarchive", {"subject": "car"})
        assert got["ok"], got
        assert rig.fake.get(f"{ROOT}/subjects/car") == whole
        assert rig.fake.get(f"{ROOT}/rev/catalog") == catalog + 2
        got = await rig.send("subject_archive", {"subject": "nope"})
        assert (got["ok"], got["code"]) == (False, "bad_request")

    run(eng, script)


def test_startup_removes_a_subject_archived_while_the_worker_was_down(
    tmp_path: Path,
) -> None:
    eng, _ = engine(tmp_path)
    _car(tmp_path / "data")
    fake = FakeRtdb()
    fake.set(f"{ROOT}/subjects/car/meta/rev", 1)  # published before
    archive.subject_archive({"subject": "car"}, eng.ctx)  # the CLI, offline
    sync = CurriculumSync(wiring(fake, eng))

    async def go() -> int:
        await sync.startup()
        count = await publish_subjects(sync)  # publish-all skips it too
        await sync.w.rtdb.aclose()
        return count

    assert asyncio.run(go()) == 0
    assert fake.get(f"{ROOT}/subjects/car") is None
    assert fake.get(f"{ROOT}/rev/catalog") == 1
    assert [e["s"] for e in fake.get(f"{ROOT}/log/{WORKER}").values()] == ["car"]


def test_home_pick_of_an_archived_subject_is_ignored(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))
    _car(tmp_path / "data")
    archive.subject_archive({"subject": "car"}, eng.ctx)

    async def script(rig: Rig) -> None:
        rig.fake.set(PICK, "car")
        got = await rig.send("session_start", {"subject": None, "card": None})
        assert got["ok"], got
        assert eng.source.subject == "automation"  # the live one, not the archive
        got = await rig.send("session_start", {"subject": "car", "card": None})
        assert (got["ok"], got["code"]) == (False, "no_card_left")

    run(eng, script)


def test_a_module_queued_before_archiving_is_not_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    _car(tmp_path / "data")
    archive.subject_archive({"subject": "car"}, eng.ctx)
    sync = CurriculumSync(wiring(FakeRtdb(), eng))
    made: list[str] = []
    monkeypatch.setattr(cur, "generate", lambda _c, s, m: made.append(f"{s}/{m}"))

    async def go() -> None:
        sync.queue.put_nowait(("car", "a"))
        task = asyncio.create_task(sync.generate_forever())
        for _ in range(100):
            await asyncio.sleep(0.01)
            if sync.queue.empty() and not sync.lock.locked():
                break
        task.cancel()
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    assert made == []
