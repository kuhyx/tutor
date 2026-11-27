# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Claude checks a card taught without it (spec Q10/Q11, part e79be0be-0).

A card read in fallback is taught and ``unchecked``. The next Claude session
of its subject opens on it before any new card, with the check section in
the prompt. A first check passed: ``checked``, FSRS kept. Failed: re-taught,
Again, ``checked``. A free-model session never checks, and marks every card
it ends ``unchecked`` (``src: free``).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor import backend_mode, check_flagged
from tutor.cards import Card, Topic
from tutor.curriculum.deck_source import DeckSource
from tutor.curriculum.eventlog import FREE, READ, UNCHECKED, unchecked_event
from tutor.curriculum.source import SubjectSource
from tutor.engine import Engine
from tutor.store import Store
from tutor.tests._cur import T0, D, H, card, make_ctx, module, subject, taught
from tutor.tests._fakes import FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.models import TutorTurn
    from tutor.session import TutorSession

PASS = {"passed": True, "feedback": "right"}
FAIL = {"passed": False, "feedback": "not yet"}
ASK = {"question": "What is thing 0?", "concept": "thing"}


def _car(root: Path) -> Context:
    """Subject ``car``: c0 read in fallback (taught + unchecked), c1 untaught."""
    ctx, _ = make_ctx(root)
    found = {f"c{i}": card("a", i) for i in range(2)}
    subject(ctx, modules=[module("a", status="ready", cards=2)], found=found)
    taught(ctx, "car", "c0", T0 - D, 1)
    ctx.log.append([unchecked_event(("car", "c0"), dev="dev-pc", at=T0 - D + 1)])
    return ctx


def _engine(root: Path, prompts: list[str], *replies: TutorTurn) -> Engine:
    fake = FakeSession(*replies)

    def factory(prompt: str) -> TutorSession:
        prompts.append(prompt)
        return fake

    clock = ManualClock(T0 / 1000)
    return Engine(store=Store(root), now=clock, session_factory=factory)


def _state(ctx: Context, cid: str = "c0") -> tuple[bool, bool, int | None]:
    got = ctx.fold().card("car", cid)
    memory = got.fsrs_state()
    due = int(memory["due"]) if memory else None
    return got.taught, got.unchecked, due


def test_start_opens_the_unchecked_card_first_with_the_check_section(
    tmp_path: Path,
) -> None:
    _car(tmp_path)
    prompts: list[str] = []
    engine = _engine(tmp_path, prompts, turn("Quick check: what is thing 0?"))
    asyncio.run(engine.start(subject="car"))
    assert engine.card is not None
    assert engine.card.id == "c0"
    assert "covered without a tutor" in prompts[-1]


def test_a_first_check_passed_clears_the_mark_and_keeps_fsrs(tmp_path: Path) -> None:
    ctx = _car(tmp_path)
    before = _state(ctx)
    prompts: list[str] = []
    replies = [
        turn("Check: what is thing 0?", check=ASK),
        turn("Right.", check_result=PASS, card_done=True),
    ]
    engine = _engine(tmp_path, prompts, *replies)
    asyncio.run(engine.start(subject="car"))
    asyncio.run(engine.reply("It is a thing."))
    assert _state(ctx) == (True, False, before[2])  # checked, not re-taught


def test_a_failed_check_reteaches_rates_again_and_clears(tmp_path: Path) -> None:
    ctx = _car(tmp_path)
    replies = [
        turn("Check: what is thing 0?", check=ASK),
        turn("Not quite; here is how it works.", check_result=FAIL),
        turn("Got it now.", check_result=PASS, card_done=True),
    ]
    engine = _engine(tmp_path, [], *replies)
    asyncio.run(engine.start(subject="car"))
    asyncio.run(engine.reply("No idea."))
    asyncio.run(engine.reply("It is a thing."))
    taught_now, marked, due = _state(ctx)
    assert (taught_now, marked) == (True, False)
    assert due is not None
    assert T0 + D <= due < T0 + D + H  # Again after the re-teach: back in a day


def test_next_card_after_the_check_opens_the_new_card(tmp_path: Path) -> None:
    _car(tmp_path)
    prompts: list[str] = []
    replies = [
        turn("Check.", check=ASK),
        turn("Right.", check_result=PASS, card_done=True),
        turn("Now thing 1."),
    ]
    engine = _engine(tmp_path, prompts, *replies)
    asyncio.run(engine.start(subject="car"))
    asyncio.run(engine.reply("It is a thing."))
    asyncio.run(engine.next_card())
    assert engine.card is not None
    assert engine.card.id == "c1"
    assert "covered without a tutor" not in prompts[-1]


def test_a_free_session_skips_the_check_and_marks_its_card(tmp_path: Path) -> None:
    ctx = _car(tmp_path)
    prompts: list[str] = []
    engine = _engine(tmp_path, prompts, turn("Thing 1."), turn("Done.", card_done=True))
    token = backend_mode.FREE.set(True)
    try:
        asyncio.run(engine.start(subject="car"))
        assert engine.card is not None
        assert engine.card.id == "c1"  # only Claude checks c0
        assert "covered without a tutor" not in prompts[-1]
        asyncio.run(engine.reply("It is a thing."))
    finally:
        backend_mode.FREE.reset(token)
    assert _state(ctx, "c1")[:2] == (True, True)
    marks = [e for e in ctx.log.read() if e["k"] == UNCHECKED and e["c"] == "c1"]
    assert [e["src"] for e in marks] == [FREE]


def test_first_grade_reads_the_transcript_then_the_current_turn(
    tmp_path: Path,
) -> None:
    ctx = _car(tmp_path)
    src = SubjectSource(Store(tmp_path), ctx, "car")
    assert check_flagged.first_grade(src, "none", {"check_result": PASS})
    assert not check_flagged.first_grade(src, "none", {"check_result": None})
    store = Store(tmp_path)
    store.log("s1", {"type": "tutor", "turn": {"check_result": FAIL}})
    store.log("s1", {"type": "learner", "text": "x"})
    assert not check_flagged.first_grade(src, "s1", {"check_result": PASS})


def test_the_old_deck_has_no_check(tmp_path: Path) -> None:
    store = Store(tmp_path)
    one = Card("io-x", "Q?", "A.", "https://e.org/x", "ex", Topic("io", "I/O", ("io",)))
    deck = DeckSource(store, [one])
    assert check_flagged.section(deck, "io-x") == ""
    check_flagged.finish(deck, "io-x", "s1", {})
    assert "io-x" in store.progress()["cards_done"]


def test_a_manual_done_in_a_free_session_marks_the_card(tmp_path: Path) -> None:
    """The learner's "Mark card done" in a free chat is weak teaching too (Q9)."""
    ctx = _car(tmp_path)
    engine = _engine(tmp_path, [], turn("Thing 1."))
    token = backend_mode.FREE.set(True)
    try:
        asyncio.run(engine.start(subject="car"))
        asyncio.run(engine.set_card_done("c1", done=True, subject="car"))
    finally:
        backend_mode.FREE.reset(token)
    asyncio.run(engine.set_card_done("c0", done=True, subject="car"))  # Claude's
    marks = [e for e in ctx.log.read() if e["k"] == UNCHECKED]
    assert [(e["c"], e.get("src")) for e in marks] == [("c0", READ), ("c1", FREE)]
