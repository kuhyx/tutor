# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The device hint: validated on every route, one note line, kept for a resume."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tutor import delivery, filler, resume
from tutor.delivery import PHONE_NOTE, Delivery
from tutor.relay import protocol
from tutor.server import create_app
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests._relay_support import engine as relay_engine
from tutor.tests.test_engine import ANSWER, CARD, events, make
from tutor.tests.test_relay_lanes import Rig, run
from tutor.tests.test_relay_protocol import RID, SID, req

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("value", "name"), [(None, "desktop"), ("desktop", "desktop"), ("phone", "phone")]
)
def test_device_absent_is_desktop(value: object, name: str) -> None:
    assert delivery.device(value) == name


@pytest.mark.parametrize("value", ["tablet", "Phone", 1, ["phone"]])
def test_an_unknown_device_is_refused(value: object) -> None:
    with pytest.raises(ValueError, match="device must be one of"):
        delivery.device(value)


def test_only_a_phone_gets_a_note_line_and_a_mark() -> None:
    assert delivery.note_lines("phone") == [PHONE_NOTE]
    assert delivery.note_lines("desktop") == []
    assert delivery.learner_message("hi", "phone") == {
        "role": "learner",
        "text": "hi",
        "device": "phone",
    }
    assert delivery.learner_message("hi", None) == {"role": "learner", "text": "hi"}


@pytest.mark.parametrize("text", ["Hint", "hint!", "Give me a hint."])
def test_a_hint_request_earns_nothing(text: str) -> None:
    assert filler.is_filler(text, check_open=True)


def test_a_phone_reply_carries_the_note_and_is_logged(tmp_path: Path) -> None:
    fake = FakeSession(turn(), turn("Short?"), turn("Long?"))
    engine = make(tmp_path, fake)
    asyncio.run(engine.start(CARD))
    state = asyncio.run(engine.reply("coil magnet", via=Delivery(device="phone")))
    asyncio.run(engine.reply(ANSWER))
    phone, desktop = str(fake.prompts[1]), str(fake.prompts[2])
    assert PHONE_NOTE in phone
    assert "device:" not in desktop  # the desktop note is today's, unchanged
    assert state["messages"][1] == {
        "role": "learner",
        "text": "coil magnet",
        "device": "phone",
    }
    logged = [e["device"] for e in events(engine) if e["type"] == "learner"]
    assert logged == ["phone", "desktop"]


def test_a_resume_keeps_the_device_and_primes_it(tmp_path: Path) -> None:
    clock = ManualClock()
    first = make(tmp_path, FakeSession(turn(), turn("Next?")), clock)
    asyncio.run(first.start(CARD))
    asyncio.run(first.reply("coil magnt", via=Delivery(device="phone")))
    path = first.store.root / "sessions" / f"{first.session_id}.jsonl"
    replayed = resume.replay(path)
    assert replayed is not None
    messages = replayed.conversation.messages
    assert messages[1]["device"] == "phone"
    assert "LEARNER (on a phone):\n<learner>\ncoil magnt" in resume.primer(messages)


def test_the_relay_message_passes_the_device(tmp_path: Path) -> None:
    eng, fake = relay_engine(tmp_path, turn("Q1?"), turn("Q2?"), turn("Q3?"))

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": None, "card": None})
        sid = got["data"]["session"]
        body = {"session": sid, "text": "magnet", "device": "phone"}
        assert (await rig.send("message", body))["ok"]
        assert (await rig.send("message", {"session": sid, "text": "x"}))["ok"]
        bad = {"session": sid, "text": "x", "device": "tablet"}
        assert (await rig.send("message", bad))["code"] == "bad_request"

    run(eng, script)
    assert PHONE_NOTE in str(fake.prompts[1])
    assert PHONE_NOTE not in str(fake.prompts[2])
    assert len(fake.prompts) == 3


def test_protocol_reads_the_device_or_defaults_it() -> None:
    got = protocol.validate(RID, req(session=SID, text="hi", device="phone"))
    assert got.body["device"] == "phone"


def test_http_message_takes_a_device_and_refuses_an_unknown_one(
    tmp_path: Path,
) -> None:
    fake = FakeSession(turn("Begin"), turn("Next"))
    eng = make(tmp_path, fake)
    with TestClient(create_app(eng, media_dirs=(tmp_path, tmp_path))) as client:
        client.post("/api/start", json={})
        body = {"text": "magnet", "device": "tablet"}
        refused = client.post("/api/message", json=body)
        assert refused.status_code == 400
        assert "device must be one of" in refused.json()["error"]
        body["device"] = "phone"
        assert client.post("/api/message", json=body).status_code == 200
    assert PHONE_NOTE in str(fake.prompts[1])
