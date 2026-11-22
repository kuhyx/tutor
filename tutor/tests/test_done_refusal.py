# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A refused ``card_done`` never reaches the learner as "this card is done".

The model is asked once more (``done_refusal.settle``); its rewrite is the
only bubble. When the rewrite fails or claims the card done again, a fixed
lock bubble naming what blocks the card is shown instead.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from tutor import done_refusal, resume
from tutor.curriculum import phase_gate
from tutor.engine import Engine
from tutor.session import Prompt, Reply, SessionError
from tutor.store import Store
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests.test_gating import (
    GATED,
    finish,
    needs,
    session_on_a_card_that_became_locked,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.models import TutorTurn
    from tutor.trace import Observer

DRAFT = "Great work, this card is done!"
REWRITE = "Before we close this one, the earlier card needs teaching. Switch?"


def events(engine: Engine, sid: str) -> list[dict[str, Any]]:
    path = engine.store.root / "sessions" / f"{sid}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()]


def missing_front(engine: Engine) -> str:
    return next(c.front for c in engine.deck if c.id == needs(engine)[-1])


def texts(state: dict[str, Any]) -> list[str]:
    return [str(m.get("text")) for m in state["messages"]]


def test_a_refused_done_shows_the_rewrite_and_never_the_draft(tmp_path: Path) -> None:
    fake = FakeSession(turn(DRAFT, card_done=True), turn(REWRITE))
    engine = session_on_a_card_that_became_locked(tmp_path, fake)
    sid = engine.session_id
    state = asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    assert texts(state)[-1] == REWRITE
    assert DRAFT not in texts(state)
    assert state["card_done"] is False
    asked = str(fake.prompts[-1])
    assert missing_front(engine) in asked
    assert "card_done" in asked
    assert needs(engine)[-1] not in asked  # the learner never reads an id
    logged = events(engine, sid)
    tutor = logged[-1]
    assert tutor["type"] == "tutor"
    assert tutor["turn"]["card_done_refused"] == [needs(engine)[-1]]
    assert tutor["ui"]["text"] == REWRITE
    rewrite = next(e for e in logged if e["type"] == "card_done_rewrite")
    assert rewrite["draft"] == DRAFT
    assert rewrite["outcome"] == "rewritten"
    assert rewrite["blockers"] == [missing_front(engine)]
    assert DRAFT not in resume.primer(engine.messages)
    replayed = resume.replay(engine.store.root / "sessions" / f"{sid}.jsonl")
    assert replayed is not None
    assert DRAFT not in [m.get("text") for m in replayed.conversation.messages]


def test_a_rewrite_that_fails_shows_the_lock_and_the_missing_front(
    tmp_path: Path,
) -> None:
    fake = FakeSession(turn(DRAFT, card_done=True), SessionError("cli died"))
    engine = session_on_a_card_that_became_locked(tmp_path, fake)
    sid = engine.session_id
    state = asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    assert texts(state)[-1] == f"{done_refusal.LOCK} {missing_front(engine)}"
    assert DRAFT not in texts(state)
    assert state["messages"][-1]["questions"] == []
    assert state["card_done"] is False
    logged = events(engine, sid)
    assert logged[-1]["turn"]["card_done_refused"] == [needs(engine)[-1]]
    outcome = next(e for e in logged if e["type"] == "card_done_rewrite")["outcome"]
    assert outcome == "fallback"


def test_a_rewrite_that_claims_done_again_shows_the_lock(tmp_path: Path) -> None:
    fake = FakeSession(
        turn(DRAFT, card_done=True, questions=("Next?",)),
        turn("Still done!", card_done=True),
    )
    engine = session_on_a_card_that_became_locked(tmp_path, fake)
    state = asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    shown = texts(state)
    assert shown[-1] == f"{done_refusal.LOCK} {missing_front(engine)}"
    assert DRAFT not in shown
    assert "Still done!" not in shown
    assert GATED not in engine.store.progress()["cards_done"]


def test_a_draft_check_result_is_kept_by_the_fallback(tmp_path: Path) -> None:
    graded = {"passed": False, "feedback": "not yet"}
    fake = FakeSession(
        turn(DRAFT, card_done=True, check_result=graded), SessionError("x")
    )
    engine = session_on_a_card_that_became_locked(tmp_path, fake)
    sid = engine.session_id
    asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    assert events(engine, sid)[-1]["turn"]["check_result"] == graded


def test_an_open_card_done_asks_no_rewrite(tmp_path: Path) -> None:
    fake = FakeSession(turn("Name them?"), turn("Done!", card_done=True))
    engine = fresh(tmp_path, fake)
    finish(engine, needs(engine))
    asyncio.run(engine.start(GATED))
    state = asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    assert state["card_done"] is True
    assert texts(state)[-1] == "Done!"
    assert len(fake.prompts) == 2


def fresh(tmp_path: Path, fake: FakeSession) -> Engine:
    return Engine(
        store=Store(tmp_path / "data"),
        now=ManualClock(),
        session_factory=lambda _prompt: fake,
    )


class _SlowRewrite(FakeSession):
    """The second ask (the rewrite) takes 30 s on the engine's clock."""

    def __init__(self, clock: ManualClock, *replies: TutorTurn) -> None:
        super().__init__(*replies)
        self.clock = clock

    async def ask(
        self, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Reply]:
        if "card_done" in str(prompt) and "refused" in str(prompt).lower():
            self.clock.advance(30)
        return await super().ask(prompt, on_trace)


def test_the_tutor_message_is_stamped_after_the_rewrite(tmp_path: Path) -> None:
    clock = ManualClock()
    first = Engine(
        store=Store(tmp_path / "data"),
        now=clock,
        session_factory=lambda _p: FakeSession(turn("Name them?")),
    )
    finish(first, needs(first))
    asyncio.run(first.start(GATED))
    first.store.unfinish_card(needs(first)[-1])
    fake = _SlowRewrite(clock, turn(DRAFT, card_done=True), turn(REWRITE))
    engine = Engine(
        store=Store(tmp_path / "data"), now=clock, session_factory=lambda _p: fake
    )
    assert engine.resume_latest() is True
    before = clock()
    asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    tutor = events(engine, engine.session_id)[-1]
    assert tutor["type"] == "tutor"
    assert tutor["t"] >= before + 30


def test_a_refusal_that_appears_only_at_apply_still_hides_the_draft(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C3 refuses the module while the image check runs: no rewrite, the lock."""
    fake = FakeSession(turn("Name them?"), turn(DRAFT, card_done=True))
    engine = fresh(tmp_path, fake)
    finish(engine, needs(engine))
    asyncio.run(engine.start(GATED))
    card = engine.card
    assert card is not None
    calls: list[int] = []

    def late(_src: object, _card: object) -> list[str]:
        calls.append(1)
        return [] if len(calls) == 1 else [card.topic.stem]

    monkeypatch.setattr(phase_gate, "blockers", late)
    state = asyncio.run(engine.reply("LD FBD ST SFC IL", msg_id="m1"))
    assert texts(state)[-1] == f"{done_refusal.LOCK} {card.topic.title}"
    assert DRAFT not in texts(state)
    assert state["card_done"] is False
    logged = events(engine, engine.session_id)
    assert logged[-1]["turn"]["card_done_refused"] == [card.topic.stem]
    late_event = next(e for e in logged if e["type"] == "card_done_rewrite")
    assert late_event["outcome"] == "late"
    assert late_event["draft"] == DRAFT


def test_names_gives_fronts_else_the_module_title(tmp_path: Path) -> None:
    engine = fresh(tmp_path, FakeSession())
    card = next(c for c in engine.deck if c.id == GATED)
    want = [next(c.front for c in engine.deck if c.id == n) for n in needs(engine)]
    assert done_refusal.names(engine.source, card, needs(engine)) == want
    # A C3 refusal blocks by module stem; an unknown id is never shown raw.
    assert done_refusal.names(engine.source, card, [card.topic.stem]) == [
        card.topic.title
    ]
    assert done_refusal.names(engine.source, card, ["no-such-card"]) == [
        card.topic.title
    ]


def test_wants_done_skips_follow_ups_and_taps(tmp_path: Path) -> None:
    engine = fresh(tmp_path, FakeSession(turn("Name them?")))
    asyncio.run(engine.start())
    conv = engine._live()[1]
    done = turn("x", card_done=True)
    assert done_refusal.wants_done(done, conv, tap=False) is True
    assert done_refusal.wants_done(done, conv, tap=True) is False
    assert done_refusal.wants_done(turn("x"), conv, tap=False) is False
    conv.follow_up = True
    assert done_refusal.wants_done(done, conv, tap=False) is False
