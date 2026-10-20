# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``follow_up_open`` over the relay: reopen a finished session, or refuse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.relay import protocol
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, engine
from tutor.tests.test_relay_lanes import Rig, run
from tutor.tests.test_relay_protocol import req

if TYPE_CHECKING:
    from pathlib import Path

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
