# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sessions/{sid}/progress``: the model's thinking and tool calls, live.

Append-only and throttled: each write carries only the steps that are new
since the last one, at most every 0.5 s for a desktop request and 2 s for a
phone one (each write is a database write and an SSE event on every device).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor.relay import live_trace
from tutor.relay.live_trace import TracePublisher
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import RIDS
from tutor.tests._trace_support import delta, search
from tutor.trace import Trace

if TYPE_CHECKING:
    import pytest

SID = "20200101-000000-abcd"
PROGRESS = f"tutor/v1/sessions/{SID}/progress"
RID = RIDS[0]


class Sleeps:
    """A fake ``asyncio.sleep`` that waits until released, and records each wait."""

    def __init__(self) -> None:
        self.waits: list[float] = []
        self.release = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)
        await self.release.wait()
        self.release.clear()


async def _settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


def test_every_is_by_the_requesting_device() -> None:
    assert live_trace.every_for({"device": "phone"}) == live_trace.PHONE_EVERY == 2.0
    assert live_trace.every_for({"device": "desktop"}) == live_trace.DESKTOP_EVERY
    assert live_trace.every_for({}) == live_trace.DESKTOP_EVERY == 0.5


def test_publisher_puts_first_then_patches_only_new_steps() -> None:
    fake = FakeRtdb()
    sleeps = Sleeps()

    async def go() -> None:
        db = fake.rtdb()
        pub = TracePublisher(db, SID, RID, every=2.0, sleep=sleeps)
        runner = asyncio.create_task(pub.run())
        t = Trace()
        t.feed(delta("Think "))
        pub.update(t)
        await _settle()  # leading edge: written at once
        assert fake.get(PROGRESS) == {
            "rid": RID,
            "steps": {"s0001": {"kind": "thinking", "text": "Think "}},
        }
        assert sleeps.waits == [2.0]
        # Three changes inside the window: ONE write, after it.
        for msg in (delta("more."), search("modbus"), delta("Then.")):
            t.feed(msg)
            pub.update(t)
        await _settle()
        writes = [w for w in fake.log if "progress" in w[1]]
        assert writes == [("PUT", f"/sessions/{SID}/progress")]
        sleeps.release.set()
        await _settle()
        assert fake.get(f"{PROGRESS}/steps") == {
            "s0001": {"kind": "thinking", "text": "Think "},
            "s0002": {"kind": "thinking", "text": "more."},
            "s0003": {"kind": "tool", "name": "WebSearch", "input": "modbus"},
            "s0004": {"kind": "thinking", "text": "Then."},
        }
        assert [w for w in fake.log if "progress" in w[1]] == [
            ("PUT", f"/sessions/{SID}/progress"),
            ("PATCH", f"/sessions/{SID}/progress/steps"),
        ]
        # A retry's fresh Trace continues after what is already shown.
        retry = Trace()
        retry.feed(delta("Again."))
        pub.update(retry)
        sleeps.release.set()
        await _settle()
        assert fake.get(f"{PROGRESS}/steps/s0005") == {
            "kind": "thinking",
            "text": "Again.",
        }
        runner.cancel()
        assert await pub.clear()
        assert fake.get(PROGRESS) is None
        await db.aclose()

    asyncio.run(go())


def test_clear_without_any_write_costs_nothing() -> None:
    fake = FakeRtdb()

    async def go() -> None:
        db = fake.rtdb()
        pub = TracePublisher(db, SID, RID, every=0.5)
        assert await pub.clear()
        assert fake.log == []
        await db.aclose()

    asyncio.run(go())


def test_a_failed_write_is_retried_on_the_next_flush(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeRtdb()
    fake.fail[("PUT", f"/sessions/{SID}/progress")] = 503
    sleeps = Sleeps()

    async def go() -> None:
        db = fake.rtdb()
        pub = TracePublisher(db, SID, RID, every=0.5, sleep=sleeps)
        runner = asyncio.create_task(pub.run())
        t = Trace()
        t.feed(delta("a"))
        pub.update(t)
        await _settle()
        assert fake.get(PROGRESS) is None
        fake.fail.clear()
        t.feed(delta("b"))
        pub.update(t)
        sleeps.release.set()
        await _settle()
        # Adjacent thinking deltas of one write are one step.
        assert fake.get(f"{PROGRESS}/steps") == {
            "s0001": {"kind": "thinking", "text": "ab"},
        }
        runner.cancel()
        await db.aclose()

    asyncio.run(go())
    assert "progress write failed" in caplog.text


def test_nothing_new_writes_nothing_and_a_failed_clear_is_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeRtdb()
    sleeps = Sleeps()

    async def go() -> None:
        db = fake.rtdb()
        pub = TracePublisher(db, SID, RID, every=0.5, sleep=sleeps)
        runner = asyncio.create_task(pub.run())
        t = Trace()
        t.feed(delta("a"))
        pub.update(t)
        await _settle()
        pub.update(t)  # the same chunks again
        sleeps.release.set()
        await _settle()
        assert [w for w in fake.log if "progress" in w[1]] == [
            ("PUT", f"/sessions/{SID}/progress")
        ]
        runner.cancel()
        fake.fail[("DELETE", f"/sessions/{SID}/progress")] = 503
        assert not await pub.clear()
        assert fake.get(PROGRESS) is not None
        await db.aclose()

    asyncio.run(go())
    assert "progress clear" in caplog.text
