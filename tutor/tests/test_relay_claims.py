# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Claims: take, lose the race, lease renewal, phases mirrored to busy; phases."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions

from tutor.relay import claims, phases
from tutor.relay.claims import Claim, claimable
from tutor.session import TutorSession
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn

if TYPE_CHECKING:
    import pytest

    from tutor.models import TutorTurn
    from tutor.session import Prompt

RID = "01M4RBCX52MMHCK7K73E6KV90H"
NOW = 1_800_000_000.0


def test_claimable() -> None:
    assert claimable(None, NOW)
    assert claimable("junk", NOW)
    assert claimable({"by": "w"}, NOW)
    assert not claimable({"by": "w", "lease_until": claims.ms(NOW) + 1}, NOW)
    assert claimable({"by": "w", "lease_until": claims.ms(NOW) - 1}, NOW)
    assert claimable({"by": "me", "lease_until": claims.ms(NOW) + 9}, NOW, "me")


def test_take_counts_attempts_and_refuses_a_live_lease() -> None:
    fake = FakeRtdb()

    async def go() -> None:
        db = fake.rtdb()
        first = Claim(db, RID, "w1", lambda: NOW)
        assert await first.take()
        assert first.attempt == 1
        node = fake.get(f"tutor/v1/requests/{RID}/claim")
        assert node["by"] == "w1"
        assert node["lease_until"] == claims.ms(NOW + claims.LEASE_S)
        assert not await Claim(db, RID, "w2", lambda: NOW).take()
        later = Claim(db, RID, "w2", lambda: NOW + claims.LEASE_S + 1)
        assert await later.take()
        assert later.attempt == 2
        await db.aclose()

    asyncio.run(go())


def test_take_loses_the_race(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeRtdb()

    async def go() -> bool:
        db = fake.rtdb()
        claim = Claim(db, RID, "w1", lambda: NOW)
        real_get = db.get_etag

        async def racing_get(path: str) -> tuple[Any, str]:
            value, tag = await real_get(path)
            fake.set(f"tutor/v1/{path}", {"by": "w2", "attempt": "x"})
            return value, tag

        monkeypatch.setattr(db, "get_etag", racing_get)
        try:
            return await claim.take()
        finally:
            await db.aclose()

    with caplog.at_level(logging.WARNING):
        assert asyncio.run(go()) is False
    assert "claimed" in caplog.text


def test_keep_renews_mirrors_busy_and_survives_a_takeover(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    fake = FakeRtdb()
    monkeypatch.setattr(claims, "RENEW_S", 0.01)
    clock = [NOW]

    async def go() -> None:
        db = fake.rtdb()
        claim = Claim(db, RID, "w1", lambda: clock[0])
        claim.busy_session, claim.busy_text = "20261012-172346-1a58", "hi"
        assert await claim.take()
        keeper = asyncio.create_task(claim.keep())
        await asyncio.sleep(0.03)
        busy = fake.get("tutor/v1/sessions/20261012-172346-1a58/meta/busy")
        assert busy == {
            "rid": RID,
            "phase": "claimed",
            "since": claims.ms(NOW),
            "text": "hi",
        }
        clock[0] += 5
        claim.set_phase("thinking")
        claim.set_phase("thinking")  # no change, no write
        await asyncio.sleep(0.03)
        node = fake.get(f"tutor/v1/requests/{RID}/claim")
        assert node["phase"] == "thinking"
        assert node["lease_until"] == claims.ms(NOW + 5 + claims.LEASE_S)
        assert (
            fake.get("tutor/v1/sessions/20261012-172346-1a58/meta/busy/phase")
            == "thinking"
        )
        fake.set(f"tutor/v1/requests/{RID}/claim", {"by": "w2"})  # taken over
        await asyncio.sleep(0.03)
        fake.fail[("PUT", f"/requests/{RID}/claim")] = 503
        await asyncio.sleep(0.03)
        keeper.cancel()
        await claim.clear_busy()
        assert fake.get("tutor/v1/sessions") is None
        await db.aclose()

    with caplog.at_level(logging.WARNING):
        asyncio.run(go())
    assert "lost to another writer" in caplog.text
    assert "claim write failed" in caplog.text


def test_clear_busy_without_a_session_is_a_no_op() -> None:
    fake = FakeRtdb()

    async def go() -> None:
        db = fake.rtdb()
        claim = Claim(db, RID, "w1", lambda: NOW)
        assert await claim.clear_busy()
        await db.aclose()

    asyncio.run(go())
    assert fake.log == []


def test_clear_busy_reports_a_failed_write(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeRtdb()
    sid = "20261012-172346-1a58"
    fake.fail[("PATCH", f"/sessions/{sid}/meta")] = 503

    async def go() -> bool:
        db = fake.rtdb()
        claim = Claim(db, RID, "w1", lambda: NOW)
        claim.busy_session = sid  # never mirrored by this claim: cleared anyway
        try:
            return await claim.clear_busy()
        finally:
            await db.aclose()

    with caplog.at_level(logging.WARNING):
        assert asyncio.run(go()) is False
    assert fake.log == [("PATCH", f"/sessions/{sid}/meta")]
    assert "busy clear" in caplog.text


class _Scripted(TutorSession):
    def __init__(self, *turns: TutorTurn) -> None:
        super().__init__(ClaudeAgentOptions())
        self.turns = list(turns)

    async def ask(self, prompt: Prompt) -> tuple[TutorTurn, Any]:
        del prompt
        return self.turns.pop(0), None


def test_phased_session_reports_each_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    sink = phases.PhaseSink()
    sink("thinking")  # no claim: dropped

    class _Claim:
        def set_phase(self, phase: str) -> None:
            seen.append(phase)

    monkeypatch.setattr(sink, "claim", _Claim())
    replies = [turn(images=[["coil"]]), turn(), turn(), turn(diagram={"x": 1})]
    monkeypatch.setattr(TutorSession, "ask", _Scripted(*replies).ask)
    factory = phases.session_factory(sink)
    session = factory("system prompt")
    assert isinstance(session, phases.PhasedSession)

    async def go() -> None:
        await session.ask("hello")
        await session.ask([{"type": "text", "text": "look"}])
        await session.ask("plain")
        await session.ask("draw")

    asyncio.run(go())
    assert seen == [
        "thinking",
        "images",
        "checking_images",
        "thinking",
        "thinking",
        "images",
    ]
