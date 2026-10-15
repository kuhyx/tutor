# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The relay while Claude is unavailable: fail fast, the drill kinds, error body."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor import unavailable
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE
from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.drill import PromptGoneError
from tutor.outage import ClaudeUnavailableError
from tutor.relay import chat
from tutor.relay.errors import classify, result_of
from tutor.tests._fakes import ManualClock, turn
from tutor.tests._relay_support import WORKER, engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path


def test_an_outage_and_its_curriculum_cause_carry_the_times() -> None:
    down = ClaudeUnavailableError("rate_limit", 1234)
    wrapped = CurriculumError(CLAUDE_UNAVAILABLE, "down")
    wrapped.__cause__ = down
    for err in (down, wrapped):
        got = result_of(classify(err))
        assert got == {
            "reason": "rate_limit",
            "resets_at": 1234,
            "ok": False,
            "code": "claude_unavailable",
            "error": "Claude is unavailable (rate_limit) until 1234",
            "retry": False,
        }
    gone = classify(PromptGoneError("gone"))
    assert (gone.code, gone.retry, gone.extra) == ("unknown_prompt", False, {})


def test_chat_kinds_fail_fast_while_claude_is_down(tmp_path: Path) -> None:
    eng, fake = engine(tmp_path, turn("Q1?"))

    async def script(rig: Rig) -> None:
        got = await rig.send("session_start", {"subject": None, "card": None})
        sid = got["data"]["session"]
        now = rig.eng.time()
        unavailable.record("overloaded", now, now + 900)
        for kind, body in (
            ("message", {"session": sid, "text": "an answer"}),
            ("next", {"session": sid}),
            ("session_resume", {"session": sid}),
            ("session_start", {"subject": None, "card": None}),
        ):
            got = await rig.send(kind, body)
            assert got["code"] == "claude_unavailable", kind
            assert (got["reason"], got["resets_at"]) == ("overloaded", int(now + 900))
        assert (await rig.send("stop", {"session": sid}))["ok"]

    run(eng, script)
    assert len(fake.prompts) == 1  # only the first start reached the model


def _taught_deck_card(tmp_path: Path) -> str:
    """Mark the deck's first card done in ``progress.json``; returns its id."""
    eng, _ = engine(tmp_path)
    first = eng.deck[0].id
    eng.store.finish_card(first, "20261015-080000-abcd")
    return first


def test_drill_over_the_relay(tmp_path: Path) -> None:
    first = _taught_deck_card(tmp_path)
    clock = ManualClock()
    eng, _ = engine(tmp_path, clock=clock)
    seen: dict[str, Any] = {}

    async def script(rig: Rig) -> None:
        asked = await rig.send("drill_next", {"subject": None})
        data = asked["data"]
        assert data["card"]["id"] == first
        assert len(data["options"]) == 4
        pending = chat._drill(rig.eng).pending
        assert pending is not None
        clock.advance(20)
        pick = {"prompt_id": data["prompt_id"], "choice": pending.answer}
        seen["answer"] = await rig.send("drill_answer", pick)
        seen["again"] = await rig.send("drill_answer", pick)
        seen["bad"] = await rig.send("drill_answer", {"prompt_id": "x", "choice": 0})
        seen["log"] = rig.fake.get(f"tutor/v1/log/{WORKER}")

    run(eng, script)
    answer = seen["answer"]["data"]
    assert (answer["correct"], answer["minute_credited"]) == (True, False)
    assert seen["again"]["code"] == "unknown_prompt"
    assert seen["bad"]["code"] == "bad_request"
    review = next(iter(eng.ctx.log.read()))
    assert (review["k"], review["c"], review["r"], review["dev"]) == (
        "review",
        first,
        3,
        WORKER,
    )
    assert review["eid"] in seen["log"]  # pushed to RTDB by the lane's sync
