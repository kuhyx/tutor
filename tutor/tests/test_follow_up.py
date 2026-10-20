# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Follow-up questions after a card is done: live at card end, or reopened."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import resume
from tutor.clock import EngagementClock
from tutor.engine import Engine
from tutor.ledger_io import default_paths
from tutor.prompt import engine_note
from tutor.prompt_rules import FOLLOW_UP
from tutor.store import Store
from tutor.tests._cur import T0
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests.test_engine_card_edits import REMOVE, _car

if TYPE_CHECKING:
    from pathlib import Path

CARD = "io-24vdc-relay-coil"
DONE = {"card_done": True, "check_result": {"passed": True, "feedback": "yes"}}
FAILED = {"check_result": {"passed": False, "feedback": "not yet"}}


def make(tmp_path: Path, fake: FakeSession, clock: ManualClock) -> Engine:
    return Engine(
        store=Store(tmp_path / "data"), now=clock, session_factory=lambda _p: fake
    )


def events(engine: Engine, sid: str) -> list[dict[str, Any]]:
    path = engine.store.root / "sessions" / f"{sid}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def finish_card(engine: Engine, clock: ManualClock, answers: int = 3) -> str:
    """Start, answer ``answers`` times 170 s apart; the last turn ends the card."""
    asyncio.run(engine.start(CARD))
    for n in range(answers):
        clock.advance(170)
        asyncio.run(engine.reply("the coil pulls the contact", msg_id=f"a{n}"))
    assert engine.state()["card_done"]
    return engine.session_id


def test_follow_up_at_card_end_is_tagged_and_never_undoes_the_card(
    tmp_path: Path,
) -> None:
    clock = ManualClock()
    fake = FakeSession(
        turn(),
        turn("Done.", **DONE),
        turn("Try this:", card_done=True, check={"question": "Q?", "concept": "x"}),
        turn("Not quite.", card_done=False, **FAILED),
    )
    engine = make(tmp_path, fake, clock)
    sid = finish_card(engine, clock, answers=1)
    clock.advance(30)
    state = asyncio.run(engine.reply("what if I just forge the name?", msg_id="f1"))
    assert state["card_done"]
    assert FOLLOW_UP in str(fake.prompts[-1])
    assert "check_due: no" in str(fake.prompts[-1])
    clock.advance(30)
    state = asyncio.run(engine.reply("no idea", msg_id="f2"))
    assert state["card_done"]  # a failed check never un-marks it
    assert CARD in engine.source.done()
    log = events(engine, sid)
    done_at = next(i for i, e in enumerate(log) if e.get("ui", {}).get("card_done"))
    after = [e for e in log[done_at + 1 :] if e["type"] in {"learner", "tutor"}]
    assert len(after) == 4
    assert all(e.get("follow_up") is True for e in after)
    assert not any(e["ui"].get("card_done") for e in after if e["type"] == "tutor")
    before = [e for e in log[:done_at] if e["type"] in {"learner", "tutor"}]
    assert not any("follow_up" in e for e in before)
    replayed = resume.replay(engine.store.root / "sessions" / f"{sid}.jsonl")
    assert replayed is not None
    assert replayed.conversation.card_done
    assert replayed.conversation.follow_up


def test_reopened_session_continues_minute_numbering(tmp_path: Path) -> None:
    """Stop, reopen 50 min later, ask: credit goes on from m9, never the gap."""
    clock = ManualClock()
    fake = FakeSession(turn(), turn(), turn(), turn("Done.", **DONE))
    engine = make(tmp_path, fake, clock)
    sid = finish_card(engine, clock)  # 3 x 170 s = 510 s: minutes 1..8
    asyncio.run(engine.stop())
    ledger = default_paths().ledger
    first = json.loads(ledger.read_text())["entries"]
    assert [r["entry_id"] for r in first] == [f"{sid}-m2", f"{sid}-m5", f"{sid}-m8"]

    clock.advance(50 * 60)
    fake.replies += [turn("A forged name fails the signature check.")]
    path = engine.store.root / "sessions" / f"{sid}.jsonl"
    state = asyncio.run(engine.follow_up_open(path))
    assert state["session_id"] == sid
    assert state["card_done"]
    clock.advance(100)
    state = asyncio.run(engine.reply("what if I write the name myself?", msg_id="f"))
    # The idle stop-to-reopen gap earned nothing; the 100 s question did.
    assert state["clock"]["active_seconds"] == pytest.approx(610.0)
    rows = json.loads(ledger.read_text())["entries"]
    ids = [r["entry_id"] for r in rows]
    assert ids == [f"{sid}-m2", f"{sid}-m5", f"{sid}-m8", f"{sid}-m10"]
    assert sum(r["detail"]["minutes"] for r in rows) == 10
    assert state["session_credited_minutes"] == 10

    replayed = resume.replay(path)
    assert replayed is not None
    assert replayed.conversation.clock.active_seconds == pytest.approx(610.0)
    assert replayed.conversation.receipts == state["receipts"]
    fresh = make(tmp_path, FakeSession(), clock)
    assert fresh.resume_path(path) is True
    assert json.loads(ledger.read_text())["entries"] == rows  # nothing minted

    asyncio.run(engine.stop())
    again = resume.replay(path)
    assert again is not None
    assert again.conversation.stopped


def test_reopen_is_refused_while_another_session_is_live(tmp_path: Path) -> None:
    clock = ManualClock()
    fake = FakeSession(turn(), turn("Done.", **DONE), turn())
    engine = make(tmp_path, fake, clock)
    old = finish_card(engine, clock, answers=1)
    asyncio.run(engine.stop())
    asyncio.run(engine.start())
    path = engine.store.root / "sessions" / f"{old}.jsonl"
    with pytest.raises(ValueError, match="stop the current session first"):
        asyncio.run(engine.follow_up_open(path))
    assert not any(e["type"] == "follow_up_open" for e in events(engine, old))


def test_reopen_of_the_live_session_changes_nothing(tmp_path: Path) -> None:
    clock = ManualClock()
    engine = make(tmp_path, FakeSession(turn(), turn("Done.", **DONE)), clock)
    sid = finish_card(engine, clock, answers=1)
    path = engine.store.root / "sessions" / f"{sid}.jsonl"
    assert asyncio.run(engine.follow_up_open(path))["session_id"] == sid
    assert not any(e["type"] == "follow_up_open" for e in events(engine, sid))


def test_reopen_needs_a_card_finished_in_that_session(tmp_path: Path) -> None:
    clock = ManualClock()
    engine = make(tmp_path, FakeSession(turn(), turn()), clock)
    asyncio.run(engine.start(CARD))
    asyncio.run(engine.reply("hm", msg_id="a"))
    sid = engine.session_id
    asyncio.run(engine.stop())
    path = engine.store.root / "sessions" / f"{sid}.jsonl"
    with pytest.raises(ValueError, match="not finished in that session"):
        asyncio.run(engine.follow_up_open(path))


def test_manual_not_done_keeps_the_follow_up_session_at_card_end(
    tmp_path: Path,
) -> None:
    clock = ManualClock()
    fake = FakeSession(turn(), turn("Done.", **DONE), turn("Sure."))
    engine = make(tmp_path, fake, clock)
    sid = finish_card(engine, clock, answers=1)
    asyncio.run(engine.reply("one more question", msg_id="f"))
    state = asyncio.run(engine.set_card_done(CARD, done=False))
    assert CARD not in engine.source.done()  # the learner's own override stands
    assert state["card_done"]  # the session stays at card end
    replayed = resume.replay(engine.store.root / "sessions" / f"{sid}.jsonl")
    assert replayed is not None
    assert replayed.conversation.card_done


def test_clock_reopened_drops_the_idle_window() -> None:
    clock = EngagementClock(0.0)
    clock.tutor_message(0.0)
    clock.server_restarted(3000.0)
    clock.reopened(3000.0)
    clock.user_reply(3100.0, "what if the name is forged?", low_effort=False)
    assert clock.active_seconds == pytest.approx(100.0)


def test_engine_note_in_follow_up_mode_never_asks_for_a_check() -> None:
    note = engine_note(900, 900, check_open=False, notes=[FOLLOW_UP])
    assert "check_due: no" in note
    assert FOLLOW_UP in note
    assert FOLLOW_UP not in engine_note(900, 900, check_open=False, notes=[])


def test_removing_the_card_in_a_follow_up_only_stops(tmp_path: Path) -> None:
    _car(tmp_path)
    fake = FakeSession(
        turn(),
        turn("Done.", **DONE),
        turn("Removed it, as you asked.", card_edits=(REMOVE,)),
    )
    engine = Engine(
        store=Store(tmp_path),
        now=ManualClock(T0 / 1000),
        session_factory=lambda _p: fake,
    )
    asyncio.run(engine.start(subject="car"))
    sid = engine.session_id
    asyncio.run(engine.reply("right", msg_id="a"))
    state = asyncio.run(engine.reply("this card is a duplicate", msg_id="f"))
    assert engine.ctx.subjects.cards("car")["c0"].suspended
    assert state["session_id"] == ""  # stopped; no next card pushed on
    assert fake.closed >= 1
    path = tmp_path / "sessions" / f"{sid}.jsonl"
    log = [json.loads(x) for x in path.read_text().splitlines()]
    assert log[-1]["type"] == "stop"
    assert not any(e["type"] == "next_card" for e in log)


def test_reopen_needs_the_card_still_in_the_deck(tmp_path: Path) -> None:
    clock = ManualClock()
    engine = make(tmp_path, FakeSession(turn(), turn("Done.", **DONE)), clock)
    sid = finish_card(engine, clock, answers=1)
    asyncio.run(engine.stop())
    path = engine.store.root / "sessions" / f"{sid}.jsonl"
    path.write_text(path.read_text().replace(CARD, "retired-card"))
    with pytest.raises(ValueError, match="gone from the deck"):
        asyncio.run(engine.follow_up_open(path))
