# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The inbox: what gets queued, lanes, garbage collection; presence; feedback."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tutor import feedback
from tutor.relay import feedback_drain, inbox, presence
from tutor.relay.inbox import Inbox
from tutor.relay.sse import Event
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import (
    PHONE,
    RIDS,
    WORKER,
    engine,
    request,
    server,
    wiring,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

NOW_MS = 1_800_000_000_000


def test_scan_queues_only_servable_requests(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    w = wiring(FakeRtdb(), eng)
    box = Inbox(w, server(w))
    stop = request("stop", {"session": "20200101-000000-abcd"})
    snapshot = {
        RIDS[0]: {"req": stop},
        RIDS[1]: {"req": request("subject_new", {"text": "x"})},
        RIDS[2]: {"req": stop, "claim": {"by": "other", "lease_until": NOW_MS * 2}},
        RIDS[3]: {"req": stop, "claim": {"by": WORKER, "lease_until": NOW_MS * 2}},
        RIDS[4]: {"req": stop, "result": {"ok": True, "at": NOW_MS}},
        RIDS[5]: {"req": stop, "result": {"ok": True, "at": 5}},
        RIDS[6]: {"claim": {"by": "x"}},
        RIDS[7]: "junk",
        RIDS[8]: {"req": "junk"},
        "not-a-ulid": {"req": stop},
    }
    box.on_event(Event("put", "/", snapshot))
    box.scan()  # idempotent: nothing queued twice, the bad key warned once
    chat = [box.queues["chat"].get_nowait() for _ in range(box.queues["chat"].qsize())]
    assert chat == [RIDS[0], RIDS[3], RIDS[8]]
    assert box.queues["build"].get_nowait() == RIDS[1]
    assert box._stale == [RIDS[5]]
    box.draining = True
    box.on_event(Event("put", f"/{RIDS[9]}/req", stop))
    assert RIDS[9] not in box.queued
    assert box.idle()
    asyncio.run(w.rtdb.aclose())


def test_watch_lane_collect_and_tick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path, turn("Q?"))
    fake = FakeRtdb()
    fake.set(
        f"tutor/v1/requests/{RIDS[5]}", {"req": {}, "result": {"ok": True, "at": 5}}
    )
    fake.set(
        f"tutor/v1/requests/{RIDS[6]}", {"req": {}, "result": {"ok": True, "at": 6}}
    )
    monkeypatch.setattr(inbox, "RESCAN_S", 0.01)

    async def go() -> None:
        w = wiring(fake, eng)
        box = Inbox(w, server(w))
        tasks = [
            asyncio.create_task(c) for c in (box.watch(), box.lane("chat"), box.tick())
        ]
        fake.fail[("DELETE", f"/requests/{RIDS[6]}")] = 503
        start = request("session_start", {"subject": None, "card": None})
        await w.rtdb.put(f"requests/{RIDS[0]}/req", start)
        for _ in range(200):
            await asyncio.sleep(0.01)
            if fake.get(f"tutor/v1/requests/{RIDS[0]}/result"):
                break
        assert fake.get(f"tutor/v1/requests/{RIDS[0]}/result/ok") is True
        await asyncio.sleep(0.05)
        assert fake.get(f"tutor/v1/requests/{RIDS[5]}") is None  # collected
        fake.fail.clear()
        await asyncio.sleep(0.05)
        assert fake.get(f"tutor/v1/requests/{RIDS[6]}") is None  # retried
        # A request vanished before its turn, and an RTDB error mid-serve.
        box.queued.add(RIDS[7])
        await box.queues["chat"].put(RIDS[7])
        fake.fail[("GET", f"/requests/{RIDS[8]}/claim")] = 500
        await w.rtdb.put(f"requests/{RIDS[8]}/req", request("stop", {}))
        await asyncio.sleep(0.05)
        assert RIDS[8] not in box.queued or fake.fail
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await w.rtdb.aclose()

    asyncio.run(go())


def test_presence_beats_measure_skew_and_leave(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb(now_ms=NOW_MS)

    async def go() -> None:
        w = wiring(fake, eng, now=lambda: NOW_MS / 1000 - 9)
        beats = presence.Presence(w, {"chat": RIDS[0], "build": None})
        await beats.beat()
        node = fake.get(f"tutor/v1/presence/workers/{WORKER}")
        assert node["beat"] == NOW_MS
        assert node["lanes"] == {"chat": RIDS[0]}
        assert beats.skew_ms == 9000
        await beats.beat()  # warned once per hour
        fake.fail[("PUT", f"/presence/workers/{WORKER}")] = 500
        task = asyncio.create_task(beats.run())
        await asyncio.sleep(0.01)
        task.cancel()
        fake.fail.clear()
        await beats.leave()
        assert fake.get("tutor/v1/presence") is None
        fake.now_ms = -1  # an odd answer
        monkeypatch.setattr(fake, "_sv", lambda value: {**value, "beat": "x"})
        await beats.beat()  # an odd answer: skew kept
        assert beats.skew_ms == 9000
        await w.rtdb.aclose()

    with caplog.at_level(logging.WARNING):
        asyncio.run(go())
    assert caplog.text.count("ms off RTDB server time") == 1
    assert "presence beat failed" in caplog.text


def test_feedback_drain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    eng, _ = engine(tmp_path, turn("Q?"))
    fake = FakeRtdb()

    async def go() -> None:
        w = wiring(fake, eng)
        assert await feedback_drain.drain(w) == 0
        await eng.start()
        sid = eng.session_id
        good = {
            "category": "ui",
            "text": "bubble cut",
            "session": sid,
            "msg": "m0001",
            "dev": PHONE,
            "route": "/s",
        }
        fake.set(f"tutor/v1/feedback/{RIDS[0]}", good)
        fake.set(f"tutor/v1/feedback/{RIDS[1]}", {"category": "nope", "text": "x"})
        fake.set(f"tutor/v1/feedback/{RIDS[2]}", "junk")
        fake.set(
            f"tutor/v1/feedback/{RIDS[3]}",
            {"category": "other", "text": "old", "session": "20200101-000000-abcd"},
        )
        fake.set("tutor/v1/feedback/bad-key", {"category": "ui", "text": "x"})
        assert await feedback_drain.drain(w) == 2
        assert set(fake.get("tutor/v1/feedback")) == {"bad-key"}
        fake.set(f"tutor/v1/feedback/{RIDS[0]}", good)  # a delete that failed
        assert await feedback_drain.drain(w) == 0
        await eng.stop()
        fake.set(f"tutor/v1/feedback/{RIDS[4]}", {**good, "text": "after stop"})
        assert await feedback_drain.drain(w) == 1
        monkeypatch.setattr(feedback_drain, "POLL_S", 0.01)
        fake.fail[("GET", "/feedback")] = 500
        task = asyncio.create_task(feedback_drain.run(w))
        await asyncio.sleep(0.03)
        task.cancel()
        await w.rtdb.aclose()

    asyncio.run(go())
    stored = feedback.load()
    assert [s["text"] for s in stored] == ["bubble cut", "old", "after stop"]
    assert stored[0]["snapshot"]["message"]["role"] == "tutor"
    assert stored[0]["fid"] == RIDS[0]
    assert stored[1]["session_id"] is None
    assert stored[2]["message_index"] == 0
