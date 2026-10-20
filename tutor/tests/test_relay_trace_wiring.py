# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The live trace's wiring: visible-thinking options, the sink, a lane, sweeps."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tutor.engine import Engine
from tutor.relay import live_trace, phases
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.claims import Claim
from tutor.relay.live_trace import TracePublisher
from tutor.session import TutorSession
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, engine, request, server, wiring
from tutor.tests._trace_support import delta, search
from tutor.trace import Trace

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.models import TutorTurn
    from tutor.session import Prompt
    from tutor.trace import Observer

SID = "20200101-000000-abcd"
PROGRESS = f"tutor/v1/sessions/{SID}/progress"
RID = RIDS[0]


def test_the_relay_session_factory_asks_for_visible_thinking() -> None:
    session = phases.session_factory(phases.PhaseSink())("system prompt")
    opts = session._options
    assert opts.thinking == {"type": "adaptive", "display": "summarized"}
    assert opts.include_partial_messages is True
    assert opts.effort == "high"


def test_the_default_engine_session_asks_for_visible_thinking() -> None:
    eng = Engine(credit_fn=lambda _u, _s: [])
    session = eng._factory("system prompt")
    assert session._options.thinking == {"type": "adaptive", "display": "summarized"}
    assert session._options.effort == "high"


def test_the_sink_routes_the_tutor_turn_trace_to_the_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Any] = []
    sink = phases.PhaseSink()

    class _Claim:
        def set_phase(self, phase: str) -> None:
            del phase

        def set_trace(self, t: Trace) -> None:
            seen.append(t.steps())

    observers: list[Observer | None] = []

    async def ask(
        self: TutorSession, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Any]:
        """Record the observer; replay one trace into it."""
        del self
        observers.append(on_trace)
        if on_trace is not None:
            t = Trace()
            t.feed(delta(f"about {prompt!s:.5}"))
            on_trace(t)
        return turn(), None

    monkeypatch.setattr(TutorSession, "ask", ask)
    session = phases.session_factory(sink)("p")

    async def go() -> None:
        await session.ask("hello")  # no claim: dropped
        monkeypatch.setattr(sink, "claim", _Claim())
        await session.ask("hello")
        await session.ask([{"type": "text", "text": "look"}])  # image check

    asyncio.run(go())
    assert observers[0] is not None
    assert observers[2] is None  # the image check is not the tutor's trace
    assert seen == [[{"kind": "thinking", "text": "about hello"}]]


# -- end to end through a lane -------------------------------------------------------


def test_a_message_streams_progress_and_clears_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    w = wiring(fake, eng)
    srv = server(w)
    rates: list[float] = []
    real = TracePublisher.__init__

    def spy(self: TracePublisher, *args: Any, **kw: Any) -> None:
        real(self, *args, **kw)
        rates.append(self.every)

    monkeypatch.setattr(TracePublisher, "__init__", spy)
    shown: list[Any] = []

    async def thinking(_ctx: object) -> dict[str, Any]:
        t = Trace()
        t.feed(delta("Let me check."))
        t.feed(search("coil"))
        w.sink.trace(t)
        for _ in range(500):
            if fake.get(PROGRESS) is not None:
                break
            await asyncio.sleep(0.001)
        shown.append(fake.get(PROGRESS))
        return {}

    monkeypatch.setitem(CHAT_HANDLERS, "message", thinking)

    async def go() -> None:
        phone = {"session": SID, "text": "hi", "device": "phone"}
        served = await srv.serve(RID, request("message", phone), "chat")
        assert served is not None
        assert served["ok"]
        desktop = {"session": SID, "text": "hi"}  # no device: the desktop
        await srv.serve(RIDS[1], request("message", desktop), "chat")
        await w.rtdb.aclose()

    asyncio.run(go())
    assert shown[0] == {
        "rid": RID,
        "steps": {
            "s0001": {"kind": "thinking", "text": "Let me check."},
            "s0002": {"kind": "tool", "name": "WebSearch", "input": "coil"},
        },
    }
    assert fake.get(PROGRESS) is None  # deleted with busy
    assert rates == [live_trace.PHONE_EVERY, live_trace.DESKTOP_EVERY]


def test_a_stale_progress_node_is_swept(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    srv = server(wiring(fake, eng))
    fake.set(PROGRESS, {"rid": RIDS[5], "steps": {"s0001": {"kind": "thinking"}}})
    srv.stale_busy.add(SID)

    async def go() -> None:
        await srv.sweep_busy()
        await srv.w.rtdb.aclose()

    asyncio.run(go())
    assert fake.get(PROGRESS) is None


def test_claim_without_progress_ignores_traces() -> None:
    fake = FakeRtdb()

    async def go() -> None:
        db = fake.rtdb()
        claim = Claim(db, RID, "w1", lambda: 1.0)
        claim.set_trace(Trace())  # no session named: nowhere to show it
        await db.aclose()

    asyncio.run(go())
    assert fake.log == []
