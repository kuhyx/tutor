# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``session_start`` ``struggle: true`` over the relay (struggle contract §5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.tests._cur import card, module, review, subject, taught
from tutor.tests._fakes import ManualClock, turn
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

HELP = {"subject": "car", "card": "c0", "struggle": True}


def test_struggle_needs_a_known_taught_card_and_skips_the_cap(tmp_path: Path) -> None:
    clock = ManualClock()
    eng, _ = engine(tmp_path, turn("What trips you up?"), clock=clock)
    ctx = eng.ctx
    found = {f"c{i}": card("a", i) for i in range(30)}
    subject(ctx, modules=[module("a", status="ready")], found=found)
    now = ctx.clock()
    for i in range(25):  # today's cap is reached
        taught(ctx, "car", f"c{i}", now - 1000 + i, i)
    for i in range(3):
        review(ctx, "car", "c0", now - 900 + i, 1)

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {**HELP, "card": None})
        assert (got["ok"], got["code"]) == (False, "bad_request")
        got = await rig.send("session_start", {**HELP, "card": "zz"})
        assert (got["ok"], got["code"]) == (False, "unknown_card")
        for lift in (False, True):  # untaught: refused before the cap, never lifted
            body = {**HELP, "lift_cap": lift, "card": "c27"}
            got = await rig.send("session_start", body)
            assert (got["ok"], got["code"]) == (False, "bad_request")
            assert "not taught" in got["error"]
        got = await rig.send("session_start", {**HELP, "lift_cap": True})
        assert got["ok"], got
        assert eng.card is not None
        assert eng.card.id == "c0"
        assert [e["k"] for e in ctx.log.read()].count("cap_lift") == 0

    run(eng, script)
