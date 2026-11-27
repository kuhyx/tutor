# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A ``session_start`` without ``free`` is a Claude start, even mid free chat.

The module gate's unchecked list (mockup F5) opens a Claude session from a
free chat to check the cards read without Claude. Were that start to ride on
the live free session, the free model would run it, never check the cards,
and the gate would refuse again for good.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import free_backend, unavailable
from tutor.tests._fakes import turn
from tutor.tests.test_free_backend import _free_engine, _up
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_a_start_without_free_leaves_the_free_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _up(monkeypatch)
    eng, seen = _free_engine(tmp_path, turn("Q1?"), turn("Q2?"))

    async def script(rig: Rig) -> None:
        now = rig.eng.time()
        unavailable.record("rate_limit", now, now + 900)
        start = {"subject": None, "card": None}
        await rig.send("session_start", {**start, "free": True})
        assert free_backend.live(rig.eng)
        claude = await rig.send("session_start", {**start, "resume": True})
        assert claude["code"] == "claude_unavailable"
        assert not free_backend.live(rig.eng)

    run(eng, script)
    assert seen == [True]
