# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Read mode over the relay: never gated by an outage, its events pushed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor import unavailable
from tutor.relay import read_kinds
from tutor.relay.errors import RequestError as RelayError
from tutor.relay.protocol import KINDS, validate
from tutor.tests._cur import card, module, subject
from tutor.tests._fakes import ManualClock
from tutor.tests._relay_support import RIDS, WORKER, engine, request
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path


def test_the_read_kinds_are_chat_kinds() -> None:
    assert KINDS["read_next"][0] == "chat"
    assert KINDS["read_rate"][0] == "chat"


_PID = "01M4QSMFG0JGMMMBEPVFB6D1AB"


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("read_next", {"subject": "Car"}),
        ("read_next", {"subject": "x" * 49}),
        ("read_next", {"subject": 3}),
        ("read_rate", {"prompt_id": "x", "rating": "got_it"}),
        ("read_rate", {"prompt_id": None, "rating": "again"}),
        ("read_rate", {"prompt_id": _PID, "rating": 1}),
    ],
)
def test_a_malformed_read_request_is_refused(kind: str, body: dict[str, Any]) -> None:
    with pytest.raises(RelayError) as err:
        validate(RIDS[0], request(kind, body))
    assert err.value.code == "bad_request"


def test_a_well_formed_read_request_passes() -> None:
    got = validate(RIDS[0], request("read_next", {"subject": "car-parts"}))
    assert got.body == {"subject": "car-parts"}
    assert validate(RIDS[0], request("read_next", {})).body == {"subject": None}
    rate = {"prompt_id": _PID, "rating": "got_it"}
    assert validate(RIDS[0], request("read_rate", rate)).body == rate


def test_read_over_the_relay_while_claude_is_down(tmp_path: Path) -> None:
    clock = ManualClock()
    eng, fake = engine(tmp_path, clock=clock)
    found = {"a1": card("a", 1), "a2": card("a", 2)}
    subject(eng.ctx, modules=[module("a", status="ready")], found=found)
    seen: dict[str, Any] = {}

    async def script(rig: Rig) -> None:
        now = rig.eng.time()
        unavailable.record("rate_limit", now, now + 900)
        asked = await rig.send("read_next", {"subject": None})
        seen["asked"] = asked
        data = asked["data"]
        assert read_kinds.read_mode(rig.eng).pending is not None
        clock.advance(20)
        rate = {"prompt_id": data["prompt_id"], "rating": "again"}
        seen["rated"] = await rig.send("read_rate", rate)
        seen["again"] = await rig.send("read_rate", rate)
        seen["bad"] = await rig.send(
            "read_rate", {"prompt_id": data["prompt_id"], "rating": "meh"}
        )
        seen["log"] = rig.fake.get(f"tutor/v1-e2e/log/{WORKER}")

    run(eng, script)
    data = seen["asked"]["data"]
    assert data["card"]["id"] == "a1"
    assert data["unavailable"]["reason"] == "rate_limit"
    rated = seen["rated"]["data"]
    assert (rated["rated"], rated["minute_credited"]) == ("again", False)
    assert seen["again"]["code"] == "unknown_prompt"
    assert seen["bad"]["code"] == "bad_request"
    events = [e for e in eng.ctx.log.read() if e["c"] == "a1"]
    assert [e["k"] for e in events] == ["taught", "unchecked", "review"]
    assert {e["dev"] for e in events} == {WORKER}
    assert all(e["eid"] in seen["log"] for e in events)  # pushed by the lane's sync
    assert not fake.prompts  # no model was asked
