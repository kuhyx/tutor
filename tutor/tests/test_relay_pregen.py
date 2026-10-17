# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``module_pregenerate`` over the relay: validated, routed, generated, locked."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor.curriculum import cardgen, judge
from tutor.relay import protocol
from tutor.tests._cur import card, module, subject
from tutor.tests._relay_support import RelayEngine, engine
from tutor.tests.test_pregen import SOURCES, drafted
from tutor.tests.test_relay_lanes import Rig, run
from tutor.tests.test_relay_protocol import RID, code_of, req

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_protocol_routes_it_to_the_build_lane() -> None:
    for modules in (["b", "c"], "all"):
        got = protocol.validate(
            RID, req("module_pregenerate", subject="car", modules=modules)
        )
        assert (got.lane, got.body) == ("build", {"subject": "car", "modules": modules})
    for bad in ("some", [], ["Bad"], 5, None, ["a"] * 49):
        raw = req("module_pregenerate", subject="car", modules=bad)
        assert code_of(raw) == "bad_request"


def test_request_queues_generation_and_the_cards_stay_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    monkeypatch.setattr(cardgen, "_sources", lambda *_: list(SOURCES))
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    subject(
        eng.ctx,
        modules=[
            module("a", status="ready", cards=1),
            module("b", "a"),
            module("c", "b"),
        ],
        found={"a-1": card("a", 1)},
    )
    assert isinstance(eng, RelayEngine)
    eng.fakes.replies.append(drafted(4))

    async def script(rig: Rig) -> None:
        sync = rig.server.curriculum
        got = await rig.send("module_pregenerate", {"subject": "car", "modules": ["b"]})
        assert got == {"ok": True, "data": {"queued": ["b"]}}
        assert sync.queue.qsize() == 1
        task = asyncio.create_task(sync.generate_forever())
        for _ in range(200):
            await asyncio.sleep(0.01)
            b = rig.fake.get("tutor/v1/subjects/car/plan")["modules"][1]
            if b["status"] != "generating":
                break
        task.cancel()
        assert (b["status"], b["cards"], b["pregenerated"]) == ("locked", 4, True)
        assert rig.fake.get("tutor/v1/subjects/car/cards/bee-0/module") == "b"
        got = await rig.send("session_start", {"subject": "car", "card": "bee-0"})
        assert got["code"] == "locked"
        got = await rig.send(
            "card_done", {"subject": "car", "card": "bee-0", "done": True}
        )
        assert got["code"] == "locked"
        got = await rig.send("module_pregenerate", {"subject": "car", "modules": ["a"]})
        assert got["code"] == "bad_request"
        edited = {
            "subject": "car",
            "card": "bee-0",
            "module": "b",
            "front": "What does a piston do?",
            "back": "It moves up and down.",
            "source": "https://en.wikipedia.org/wiki/Piston",
            "excerpt": "a piston is a moving part that slides in a cylinder",
            "requires": [],
        }
        got = await rig.send("card_edit", edited)  # reviewable before it opens
        assert got == {"ok": True, "data": {"card": "bee-0", "rev": 2}}
        b = rig.fake.get("tutor/v1/subjects/car/plan")["modules"][1]
        assert (b["status"], b["pregenerated"]) == ("locked", True)

    run(eng, script)
