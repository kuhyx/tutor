# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A tapped answer to the comprehension check never passes it on its own."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from tutor import history, picked
from tutor.engine import Engine
from tutor.models import TutorTurn
from tutor.relay import views
from tutor.store import Store
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

CARD = "io-24vdc-relay-coil"
OPTIONS = ["24 V DC", "230 V AC", "5 V DC"]
CHECK: dict[str, Any] = {
    "question": "Which coil voltage is typical?",
    "concept": "coil voltage",
    "choices": OPTIONS,
}
PASS = {"passed": True, "feedback": "Right."}
FAIL = {"passed": False, "feedback": "Not yet."}
TAP = "Q1: Which coil voltage is typical?\nA: 24 V DC (picked option)"
TYPED = "Q1: Which coil voltage is typical?\nA: 24 V DC, the usual control supply"
WHY_TYPED = (
    "Q1: Why is that the right answer?\nA: it is the standard safe control voltage"
)


def raw(**over: Any) -> dict[str, Any]:
    """The model's check turn as it arrives, before repair."""
    found: dict[str, Any] = {
        "message": "Check time.",
        "low_effort": False,
        "questions": [],
        "check": CHECK,
        "check_result": None,
        "images": [],
        "diagram": None,
        "concepts_mastered": [],
        "card_done": False,
    }
    return found | over


def posed() -> TutorTurn:
    """The check turn, through the same repair as a real reply."""
    return TutorTurn.from_json(raw())


def make(tmp_path: Path, *replies: TutorTurn) -> tuple[Engine, FakeSession]:
    fake = FakeSession(posed(), *replies)
    engine = Engine(
        store=Store(tmp_path / "data"),
        now=ManualClock(),
        credit_fn=FakeCredit(),
        session_factory=lambda _prompt: fake,
    )
    asyncio.run(engine.start(CARD))
    return engine, fake


def tutor_log(engine: Engine) -> list[dict[str, Any]]:
    path = engine.store.root / "sessions" / f"{engine.session_id}.jsonl"
    events = [json.loads(line) for line in path.read_text().splitlines()]
    return [e["turn"] for e in events if e["type"] == "tutor"]


def passed_so_far(engine: Engine) -> int:
    conv = engine._conv
    assert conv is not None
    return conv.check.passed


def test_tapped_finds_only_an_answer_line_ending_in_the_marker() -> None:
    assert picked.tapped(TAP)
    assert picked.tapped(f"{TAP}  \n\nComment: hi")
    assert not picked.tapped(TYPED)
    assert not picked.tapped("Comment: (picked option)")
    assert not picked.tapped("A: (picked option) then more")
    assert picked.note(tap=False) == []
    assert picked.note(tap=True) == [picked.NOTE]


def test_the_check_carries_three_mixed_choices_to_the_page(tmp_path: Path) -> None:
    engine, _ = make(tmp_path)
    check = engine.state()["messages"][-1]["check"]
    assert check["question"] == CHECK["question"]
    assert sorted(check["choices"]) == sorted(OPTIONS)
    assert tutor_log(engine)[0]["check"]["choices"] == check["choices"]
    # The phone reads it from the relay projection (``check`` is passed whole).
    deck = history.View({c.id: c.front for c in engine.deck}, "", set(), set())
    src = views.Sources(deck, engine.time(), lambda _r: None, lambda _p: None)
    doc = views.build(engine.store.root / "sessions", engine.session_id, src)
    assert doc is not None
    assert doc.msgs["m0001"]["check"] == check


def test_a_bad_check_choice_list_becomes_empty() -> None:
    bad = {**CHECK, "choices": ["a", "a", "b"]}
    assert TutorTurn.from_json(raw(check=bad)).check == {**CHECK, "choices": []}
    assert TutorTurn.from_json(raw(check=None)).check is None


def test_a_tapped_right_answer_is_refused_and_a_why_is_asked(tmp_path: Path) -> None:
    graded = turn(
        "Correct, card done!",
        check_result=PASS,
        concepts_mastered=("coil voltage",),
        card_done=True,
    )
    engine, fake = make(tmp_path, graded, turn("Good.", check_result=PASS))
    state = asyncio.run(engine.reply(TAP, msg_id="m1"))
    assert picked.NOTE in str(fake.prompts[-1])
    last = state["messages"][-1]
    assert last["check_result"] is None
    assert last["check"] == {
        "question": picked.WHY,
        "concept": "coil voltage",
        "choices": [],
    }
    assert "mastered_new" not in last
    assert not last.get("card_done")
    assert (state["check_open"], state["card_done"]) == (True, False)
    assert engine.source.mastered() == []
    assert passed_so_far(engine) == 0
    logged = tutor_log(engine)[-1]
    assert logged["check_result"] is None
    assert logged["check_result_refused"] == PASS
    assert logged["concepts_refused"] == ["coil voltage"]
    assert (logged["card_done"], logged["card_done_tapped"]) == (False, True)
    # The typed why is what passes.
    state = asyncio.run(engine.reply(WHY_TYPED, msg_id="m2"))
    assert picked.REFUSED in str(fake.prompts[-1])
    assert picked.NOTE not in str(fake.prompts[-1])
    assert state["check_open"] is False
    assert passed_so_far(engine) == 1


def test_the_models_own_why_stays_but_loses_its_choices(tmp_path: Path) -> None:
    why = {"question": "Why that one?", "concept": "coil voltage", "choices": OPTIONS}
    engine, fake = make(tmp_path, turn("Right - but why?", check=why))
    state = asyncio.run(engine.reply(TAP, msg_id="m1"))
    assert state["messages"][-1]["check"] == {**why, "choices": []}
    assert state["check_open"] is True
    assert "check_result_refused" not in tutor_log(engine)[-1]
    assert engine._conv is not None
    assert picked.REFUSED not in engine._conv.notes
    assert len(fake.prompts) == 2


def test_an_ungraded_tap_gets_a_neutral_why(tmp_path: Path) -> None:
    engine, _ = make(tmp_path, turn("Hmm, tell me more."))
    state = asyncio.run(engine.reply(TAP, msg_id="m1"))
    assert state["messages"][-1]["check"]["question"] == picked.WHY_UNGRADED
    assert state["check_open"] is True
    assert "check_result_refused" not in tutor_log(engine)[-1]


def test_a_tapped_wrong_answer_is_graded_like_a_typed_one(tmp_path: Path) -> None:
    retry = turn("Not quite.", check_result=FAIL, check=posed().check)
    engine, _ = make(tmp_path, retry)
    state = asyncio.run(engine.reply(TAP, msg_id="m1"))
    last = state["messages"][-1]
    assert last["check_result"] == FAIL
    assert sorted(last["check"]["choices"]) == sorted(OPTIONS)  # attempt 2
    assert state["check_open"] is True
    assert engine._conv is not None
    assert engine._conv.check.attempt == 2


def test_a_typed_right_answer_passes_as_before(tmp_path: Path) -> None:
    done = turn("Yes.", check_result=PASS, card_done=True)
    engine, fake = make(tmp_path, done)
    state = asyncio.run(engine.reply(TYPED, msg_id="m1"))
    assert picked.NOTE not in str(fake.prompts[-1])
    assert state["messages"][-1]["check_result"] == PASS
    assert (state["check_open"], state["card_done"]) == (False, True)
    assert passed_so_far(engine) == 1


def test_a_tap_with_no_check_open_is_left_alone(tmp_path: Path) -> None:
    graded = turn("Yes.", check_result=PASS, card_done=True)
    engine, fake = make(tmp_path, graded, turn("Done.", card_done=True))
    asyncio.run(engine.reply(TYPED, msg_id="m1"))  # the check passes, closes
    state = asyncio.run(engine.reply(TAP, msg_id="m2"))
    assert picked.NOTE not in str(fake.prompts[-1])
    assert state["card_done"] is True


def test_replay_keeps_the_refusal(tmp_path: Path) -> None:
    graded = turn("Correct!", check_result=PASS, card_done=True)
    engine, _ = make(tmp_path, graded)
    asyncio.run(engine.reply(TAP, msg_id="m1"))
    again = Engine(
        store=engine.store,
        now=ManualClock(),
        credit_fn=FakeCredit(),
        session_factory=lambda _prompt: FakeSession(),
    )
    assert again.resume_latest() is True
    state = again.state()
    assert (state["check_open"], state["card_done"]) == (True, False)
    assert passed_so_far(again) == 0
