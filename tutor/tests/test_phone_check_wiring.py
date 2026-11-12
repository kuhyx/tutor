# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Where the phone check is triggered: the relay's task and every served request."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from tutor.relay import plan, worker
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.lanes import Server
from tutor.relay.phases import PhaseSink
from tutor.store import data_dir
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import RIDS, engine, request, wiring

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_serving_a_request_pokes_the_phone_check(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    w = wiring(fake, eng)
    poked: list[int] = []
    server = Server(w, CurriculumSync(w), poke=lambda: poked.append(1))
    req = request("plan_today", {}, created=int(eng.time() * 1000))
    fake.set(f"tutor/v1-e2e/requests/{RIDS[0]}/req", req)
    result = asyncio.run(server.serve(RIDS[0], req, "chat"))
    assert result is not None
    assert result["ok"] is True
    assert poked == [1]


def test_the_relay_runs_the_check_and_pokes_it_per_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    ticks: list[int] = []

    async def go() -> worker.Relay:
        relay = worker.Relay(eng, fake.rtdb(), PhaseSink(), eng.time)

        async def tick() -> None:
            ticks.append(1)

        monkeypatch.setattr(relay.phone, "tick", tick)
        async with worker.running(relay):
            await relay.ready.wait()
            await asyncio.sleep(0.05)
        return relay

    relay = asyncio.run(go())
    assert ticks
    assert relay.server.poke == relay.phone.poke


def test_has_steps_sees_a_written_plan_only() -> None:
    assert plan.has_steps("2027-01-15") is False
    path = data_dir() / "plan" / "2027-01-15.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"steps": []}), encoding="utf-8")
    assert plan.has_steps("2027-01-15") is False
    step = {"id": "s", "title": "s", "what": "w", "kind": "note", "target": ""}
    path.write_text(json.dumps({"steps": [step]}), encoding="utf-8")
    assert plan.has_steps("2027-01-15") is True
