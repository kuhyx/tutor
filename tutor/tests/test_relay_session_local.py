# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The relay's sessions (the app's path) answer locally when Claude is spent."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor import local_model
from tutor.local_session import FallbackSession
from tutor.outage import ClaudeUnavailableError
from tutor.relay import phases
from tutor.tests.test_local_session import Claude, Local, _turn

if TYPE_CHECKING:
    import pytest


def test_a_relay_session_falls_back_to_the_local_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Claude(monkeypatch, ClaudeUnavailableError("rate_limit", 1))
    local = Local(_turn("What does PLC stand for?"))
    monkeypatch.setattr(local_model, "chat", local)
    session = phases.session_factory(phases.PhaseSink())("SYS")
    assert isinstance(session, FallbackSession)

    async def go() -> None:
        turn, reply = await session.ask("Start the card.")
        assert turn.message == "What does PLC stand for?"
        assert reply.init["model"] == local_model.MODEL

    asyncio.run(go())
    assert len(local.calls) == 1
