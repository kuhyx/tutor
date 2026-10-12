# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Serving requests end to end on the fake RTDB: chat kinds, errors, dedupe."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay import claims
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.rtdb import RtdbError
from tutor.session import SessionError
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, engine, request, server, wiring

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from tutor.engine import Engine


class Rig:
    """A server on the fake database; ``send`` PUTs a req and serves it."""

    def __init__(self, eng: Engine) -> None:
        self.fake = FakeRtdb()
        self.eng = eng
        self.w = wiring(self.fake, eng)
        self.server = server(self.w)
        self.n = 0

    async def send(self, kind: str, body: dict[str, Any], **kw: Any) -> Any:
        rid = RIDS[self.n]
        self.n += 1
        req = request(kind, body, created=int(self.eng.time() * 1000), **kw)
        self.fake.set(f"tutor/v1/requests/{rid}/req", req)
        return await self.server.serve(rid, req, "chat")


def run(eng: Engine, script: Callable[[Rig], Awaitable[None]]) -> Rig:
    rig = Rig(eng)

    async def go() -> None:
        try:
            await script(rig)
        finally:
            await rig.w.rtdb.aclose()

    asyncio.run(go())
    return rig


def test_start_message_next_stop(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Q2?"), turn("Next card Q?"))

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": None, "card": None})
        sid = got["data"]["session"]
        assert got["ok"]
        assert rig.fake.get(f"tutor/v1/requests/{RIDS[0]}/result/at") == rig.fake.now_ms
        assert rig.fake.get(f"tutor/v1/sessions/{sid}/meta/n") == 1
        got = await rig.send("message", {"session": sid, "text": "an answer"})
        assert got["data"] == {"msg": "m0003"}
        learner = rig.fake.get(f"tutor/v1/sessions/{sid}/msgs/m0002")
        assert learner["rid"] == RIDS[1]
        assert learner["dev"] is None or isinstance(learner["dev"], str)
        got = await rig.send("next", {"session": sid})
        assert got["data"]["session"] != sid
        new = got["data"]["session"]
        assert rig.fake.get(f"tutor/v1/sessions/{sid}/meta/stopped") is True
        assert rig.fake.get("tutor/v1/live/session") == new
        got = await rig.send("stop", {"session": new})
        assert got == {"ok": True, "data": {}}
        assert rig.fake.get("tutor/v1/live") is None

    rig = run(eng, script)
    assert (rig.w.done.get(RIDS[1]) or {})["kind"] == "message"


def test_learner_time_is_server_receipt_or_send_press(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"), turn("Q2?"), turn("Q3?"))

    async def script(rig: Rig) -> None:
        sid = (await rig.send("session_start", {"subject": None, "card": None}))[
            "data"
        ]["session"]
        now = int(eng.time() * 1000)
        for sent in (now - 100_000, now + 50_000):  # within grace / later than created
            rid = RIDS[rig.n]
            rig.n += 1
            req = request("message", {"session": sid, "text": "x"}, created=now - 7_000)
            req["sent_at"] = sent
            await rig.server.serve(rid, req, "chat")
        path = eng.store.root / "sessions" / f"{sid}.jsonl"
        learners = [
            json.loads(x) for x in path.read_text().splitlines() if '"learner"' in x
        ]
        assert [e["t"] for e in learners] == [
            (now - 100_000) / 1000,
            (now - 7_000) / 1000,
        ]

    run(eng, script)


def test_errors_become_results(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"), SessionError("cli died"))

    async def script(rig: Rig) -> None:
        sid = (await rig.send("session_start", {"subject": None, "card": None}))[
            "data"
        ]["session"]
        got = await rig.send("message", {"session": sid, "text": "boom"})
        assert (got["code"], got["retry"]) == ("model_error", True)
        got = await rig.send(
            "message", {"session": "20200101-000000-abcd", "text": "x"}
        )
        assert got["code"] == "not_live"
        got = await rig.send("session_start", {"subject": "car", "card": None})
        assert got["code"] == "bad_request"
        got = await rig.send("subject_new", {"text": "cars"})
        assert got["code"] == "worker_error"
        assert got["error"] == "worker error: IndexError"  # the fake model had no reply
        got = await rig.send("bogus", {})
        assert got["code"] == "bad_request"
        got = await rig.send(
            "card_done", {"subject": None, "card": "nope-x", "done": True}
        )
        assert got["code"] == "unknown_card"
        got = await rig.send(
            "card_done", {"subject": None, "card": eng.deck[0].id, "done": True}
        )
        assert got["ok"]

    run(eng, script)


def test_done_map_answers_again_without_running(tmp_path: Path) -> None:
    eng, fake_session = engine(tmp_path, turn("Q1?"))

    async def script(rig: Rig) -> None:
        req = request("session_start", {"subject": None, "card": None})
        first = await rig.server.serve(RIDS[0], req, "chat")
        rig.fake.set(f"tutor/v1/requests/{RIDS[0]}", None)  # GC'd
        again = await rig.server.serve(RIDS[0], req, "chat")
        assert again == first
        assert rig.fake.get(f"tutor/v1/requests/{RIDS[0]}/result/ok") is True

    run(eng, script)
    assert len(fake_session.prompts) == 1


def test_live_lease_elsewhere_and_gave_up(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)

    async def script(rig: Rig) -> None:
        held = {
            "by": "other",
            "lease_until": int(eng.time() * 1000) + 60_000,
            "attempt": 1,
        }
        rig.fake.set(f"tutor/v1/requests/{RIDS[0]}/claim", held)
        assert await rig.server.serve(RIDS[0], request("stop", {}), "chat") is None
        tired = {"by": "other", "lease_until": 0, "attempt": claims.MAX_ATTEMPTS}
        rig.fake.set(f"tutor/v1/requests/{RIDS[1]}/claim", tired)
        got = await rig.server.serve(RIDS[1], request("stop", {}), "chat")
        assert (got or {})["code"] == "gave_up"

    run(eng, script)


def test_publish_failure_still_answers(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))

    async def script(rig: Rig) -> None:
        rig.fake.fail[("PUT", "/live")] = 503
        got = await rig.send("session_start", {"subject": None, "card": None})
        assert got["ok"]

    run(eng, script)
    assert "publish after" in caplog.text


def test_curriculum_sync_failure_does_not_fail_the_request(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    eng, _ = engine(tmp_path, turn("Q1?"))

    async def script(rig: Rig) -> None:
        rig.fake.fail[("GET", "/log")] = 503
        got = await rig.send("session_start", {"subject": None, "card": None})
        assert got["ok"]

    run(eng, script)
    assert "curriculum sync failed" in caplog.text


class UnexpectedBugError(Exception):
    """Not an error a handler may report: a bug."""


def test_unexpected_errors_propagate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)

    async def broken(_ctx: object) -> dict[str, Any]:
        raise UnexpectedBugError

    monkeypatch.setitem(CHAT_HANDLERS, "stop", broken)

    async def script(rig: Rig) -> None:
        with pytest.raises(UnexpectedBugError):
            await rig.send("stop", {"session": "20200101-000000-abcd"})

    run(eng, script)


def test_rtdb_error_from_result_put_propagates(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)

    async def script(rig: Rig) -> None:
        rig.fake.fail[("PUT", f"/requests/{RIDS[0]}/result")] = 500
        with pytest.raises(RtdbError):
            await rig.send("bogus", {})
        assert rig.w.done.get(RIDS[0]) is not None  # committed before the PUT

    run(eng, script)
