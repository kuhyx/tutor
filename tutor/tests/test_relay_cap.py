# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``session_start`` over the relay: the cap's payload and ``lift_cap``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.curriculum import cap
from tutor.tests._cur import card, module, subject, taught
from tutor.tests._fakes import ManualClock, turn
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

START = {"subject": "hosting", "card": None}


def test_lift_cap_starts_the_session_and_lifts_once_per_day(tmp_path: Path) -> None:
    clock = ManualClock()
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Q2?"), turn("Q3?"), clock=clock)
    ctx = eng.ctx
    mods = [module("a", status="ready")]
    mods[0].title = "vhost-apache"
    subject(
        ctx, "hosting", modules=mods, found={f"c{i}": card("a", i) for i in range(30)}
    )
    now = ctx.clock()
    for i in range(25):
        taught(ctx, "hosting", f"c{i}", now - 1000 + i, i)

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", START)
        assert (got["ok"], got["code"]) == (False, "daily_new_cap")
        assert got["next"] == "lift_cap"
        assert (got["new_today"], got["new_cap"]) == (25, 25)
        assert got["module_title"] == "vhost-apache"
        assert got["subject_title"] == "Cars"
        assert got["due_in_subject"] == 0
        got = await rig.send("session_start", {**START, "lift_cap": True})
        assert got["ok"], got
        assert eng.card is not None
        assert eng.card.id == "c25"
        got = await rig.send("session_start", {**START, "lift_cap": True})
        assert got["ok"], got
        assert [e["k"] for e in eng.ctx.log.read()].count("cap_lift") == 1
        clock.advance(86_400)  # the next day: the lift is gone
        assert not cap.lifted_today(eng.ctx.fold(), eng.ctx.clock())
        got = await rig.send("session_start", {**START, "lift_cap": False})
        assert got["ok"], got  # nothing new taught today: under the cap
        assert [e["k"] for e in eng.ctx.log.read()].count("cap_lift") == 1

    run(eng, script)
