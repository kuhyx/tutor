# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``follow_up_open`` over the relay: reopen a finished session, or refuse."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tutor.relay import phases, protocol
from tutor.session import TutorSession
from tutor.tests._fakes import FakeSession, turn
from tutor.tests._relay_support import RIDS, engine
from tutor.tests._trace_support import delta
from tutor.tests.test_relay_lanes import Rig, run
from tutor.tests.test_relay_protocol import req
from tutor.trace import Trace

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.models import TutorTurn
    from tutor.session import Prompt, Reply
    from tutor.trace import Observer

DONE = {"card_done": True, "check_result": {"passed": True, "feedback": "ok"}}


def test_follow_up_open_kind_validates() -> None:
    sid = "20261020-172115-3f84"
    got = protocol.validate(RIDS[0], req("follow_up_open", session=sid))
    assert got.lane == protocol.CHAT
    assert got.body == {"session": sid}


def test_reopen_a_stopped_session_then_ask(tmp_path: Path) -> None:
    eng, _ = engine(
        tmp_path, turn("Q?"), turn("Done.", **DONE), turn("Q2?"), turn("Because.")
    )

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": None, "card": None})
        first = got["data"]["session"]
        assert (await rig.send("message", {"session": first, "text": "x"}))["ok"]
        assert (await rig.send("stop", {"session": first}))["ok"]
        meta = f"tutor/v1/sessions/{first}/meta"
        assert rig.fake.get(f"{meta}/stopped") is True
        got = await rig.send("follow_up_open", {"session": first})
        assert got["data"] == {"session": first}
        assert rig.fake.get(f"{meta}/stopped") is False
        assert rig.fake.get(f"{meta}/card_done") is True
        assert rig.fake.get("tutor/v1/live/session") == first
        got = await rig.send("message", {"session": first, "text": "what if?"})
        assert got["ok"]
        # Another session live: refused, with a code the app can explain.
        second = (await rig.send("session_start", {"subject": None, "card": None}))[
            "data"
        ]["session"]
        assert second != first
        got = await rig.send("follow_up_open", {"session": first})
        assert got["code"] == "session_live"
        assert "stop the current session first" in got["error"]
        got = await rig.send("follow_up_open", {"session": "20200101-000000-abcd"})
        assert got["code"] == "bad_request"

    run(eng, script)


def test_follow_up_turns_show_their_trace_live_and_keep_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both ways into follow-up mode go through the traced relay session."""
    replies = (turn("Q?"), turn("Done.", **DONE), turn("At end."), turn("Reopened."))
    eng, fake = engine(tmp_path, *replies)
    live: list[Any] = []
    rigs: list[Rig] = []

    async def ask(
        self: TutorSession, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Reply]:
        """The scripted reply; its trace goes to ``on_trace`` and stays with it."""
        del self
        got, reply = await FakeSession.ask(fake, prompt)
        trace = Trace()
        trace.feed(delta(f"thinking {len(fake.prompts)}"))
        assert on_trace is not None  # the relay session always observes
        on_trace(trace)
        node = f"tutor/v1/sessions/{eng.session_id}/progress"
        for _ in range(500):
            if (seen := rigs[0].fake.get(node)) is not None:
                break
            await asyncio.sleep(0.001)
        live.append(seen)
        reply.trace = trace.steps()
        return got, reply

    monkeypatch.setattr(TutorSession, "ask", ask)

    async def script(rig: Rig) -> None:
        rigs.append(rig)
        eng._factory = phases.session_factory(rig.w.sink)  # as relay_engine does
        sid = (await rig.send("session_start", {"subject": None, "card": None}))[
            "data"
        ]["session"]
        for text in ("x", "and at card end?"):
            assert (await rig.send("message", {"session": sid, "text": text}))["ok"]
        assert (await rig.send("stop", {"session": sid}))["ok"]
        assert (await rig.send("follow_up_open", {"session": sid}))["ok"]
        assert (await rig.send("message", {"session": sid, "text": "again?"}))["ok"]
        assert rig.fake.get(f"tutor/v1/sessions/{sid}/progress") is None

    run(eng, script)
    # live[0]: session_start names no session yet, so it has no progress node.
    assert [s["steps"]["s0001"]["text"] for s in live[1:]] == [
        f"thinking {n}" for n in range(2, 5)
    ]
    tutor = [m for m in eng.messages if m["role"] == "tutor"]
    assert [m["trace"] for m in tutor[-2:]] == [
        [{"kind": "thinking", "text": "thinking 3"}],
        [{"kind": "thinking", "text": "thinking 4"}],
    ]
