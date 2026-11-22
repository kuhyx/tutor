# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C3 at the engine's entry points: start, reply, resume, follow-up, card_done.

Every way into teaching a card of a gated module, or marking one taught,
refuses while the guard does not list the module; refused is the existing
"nothing to teach" (``no_card_left``) or ``locked`` state, never new text.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum.errors import LOCKED, NO_CARD_LEFT, RequestError
from tutor.engine import Engine
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject, taught
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import FakeSession, ManualClock, turn
from tutor.tests._phase import LC, grant, phase_row, write_phase
from tutor.tests._relay_support import engine as relay_engine
from tutor.tests._relay_support import wiring

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from pathlib import Path

    from tutor.models import TutorTurn
    from tutor.session import Prompt
    from tutor.session_types import Observer, Reply

DONE = {"card_done": True, "check_result": {"passed": True, "feedback": "yes"}}
SOLVE = phase_row([], phase="solve")


class FlipSession(FakeSession):
    """The guard moves to SOLVE while the model is answering ask number ``at``."""

    def __init__(self, at: int, *replies: TutorTurn) -> None:
        """Flip during the ``at``-th ask (1-based)."""
        super().__init__(*replies)
        self.at = at

    async def ask(
        self, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Reply]:
        """Flip the phase, then answer as scripted."""
        if len(self.prompts) + 1 == self.at:
            write_phase(SOLVE)
        return await super().ask(prompt, on_trace)


def _engine(root: Path, fake: FakeSession) -> Engine:
    ctx, _ = make_ctx(root)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {"a0": card("a", 0), "a1": card("a", 1), "b0": card("b", 0)}
    subject(ctx, LC, modules=mods, found=found)
    return Engine(store=Store(root), now=ManualClock(), session_factory=lambda _: fake)


def _code(call: Awaitable[Any]) -> str:
    with pytest.raises(RequestError) as err:
        asyncio.run(call)
    return err.value.code


def _sessions(root: Path) -> list[Path]:
    return sorted((root / "sessions").glob("*.jsonl"))


def test_start_and_struggle_refuse_a_refused_module(tmp_path: Path) -> None:
    write_phase(SOLVE)
    engine = _engine(tmp_path, FakeSession())
    taught(engine.ctx, LC, "a0", 1_800_000_000_000)
    assert _code(engine.start(subject=LC)) == NO_CARD_LEFT
    assert _code(engine.start("a1", subject=LC)) == NO_CARD_LEFT
    assert _code(engine.start("a0", subject=LC, struggling=True)) == NO_CARD_LEFT
    assert engine.source.subject == "automation"
    assert _sessions(tmp_path) == []


def test_next_card_skips_a_refused_module(tmp_path: Path) -> None:
    grant((LC, "a"))
    done = turn("Done.", **DONE)
    engine = _engine(tmp_path, FakeSession(turn(), done, turn(), done))
    assert asyncio.run(engine.start(subject=LC))["card"]["id"] == "a0"
    asyncio.run(engine.reply("the answer"))
    assert asyncio.run(engine.next_card())["card"]["id"] == "a1"
    asyncio.run(engine.reply("the answer"))
    assert engine.ctx.fold().taught_ids(LC) == {"a0", "a1"}
    assert _code(engine.next_card()) == NO_CARD_LEFT  # b0 is refused


def test_a_reply_on_a_card_that_became_refused_never_reaches_the_model(
    tmp_path: Path,
) -> None:
    grant((LC, "a"))
    fake = FakeSession(turn())
    engine = _engine(tmp_path, fake)
    asyncio.run(engine.start(subject=LC))
    write_phase(SOLVE)
    assert _code(engine.reply("an answer")) == NO_CARD_LEFT
    assert len(fake.prompts) == 1  # only the opening turn
    assert engine.ctx.fold().taught_ids(LC) == set()


def test_a_card_done_while_the_phase_flips_is_not_marked(tmp_path: Path) -> None:
    grant((LC, "a"))
    engine = _engine(tmp_path, FlipSession(2, turn(), turn("Done.", **DONE)))
    asyncio.run(engine.start(subject=LC))
    state = asyncio.run(engine.reply("the answer"))
    assert not state["card_done"]
    assert engine.ctx.fold().taught_ids(LC) == set()
    lines = [json.loads(x) for x in _sessions(tmp_path)[0].read_text().splitlines()]
    (logged,) = [e["turn"] for e in lines if e["type"] == "tutor"][1:]
    assert (logged["card_done"], logged["card_done_refused"]) == (False, ["a"])


def test_resume_and_continue_refuse_a_refused_module(tmp_path: Path) -> None:
    grant((LC, "a"))
    live = _engine(tmp_path, FakeSession(turn()))
    asyncio.run(live.start(subject=LC))
    path = _sessions(tmp_path)[0]
    write_phase(SOLVE)
    again = _engine(tmp_path, FakeSession())
    assert not again.resume_latest()
    assert not again.resume_path(path)
    with pytest.raises(ValueError, match="cannot be continued"):
        asyncio.run(again.resume_session(path))
    assert not asyncio.run(again.continue_subject(LC))  # falls through to start
    grant((LC, "a"))
    assert asyncio.run(again.continue_subject(LC))
    assert again.card is not None
    assert again.card.id == "a0"


def test_follow_up_on_a_refused_module_is_refused(tmp_path: Path) -> None:
    grant((LC, "a"))
    engine = _engine(tmp_path, FakeSession(turn(), turn("Done.", **DONE)))
    asyncio.run(engine.start("a0", subject=LC))
    assert asyncio.run(engine.reply("the answer"))["card_done"]
    asyncio.run(engine.stop())
    write_phase(SOLVE)
    path = _sessions(tmp_path)[0]
    with pytest.raises(ValueError, match="cannot be continued"):
        asyncio.run(engine.follow_up_open(path))
    assert "follow_up_open" not in path.read_text()


def test_manual_mark_done_is_refused_but_undo_is_not(tmp_path: Path) -> None:
    write_phase(SOLVE)
    engine = _engine(tmp_path, FakeSession())
    assert _code(engine.set_card_done("a0", done=True, subject=LC)) == LOCKED
    taught(engine.ctx, LC, "a1", 1_800_000_000_000)
    asyncio.run(engine.set_card_done("a1", done=False, subject=LC))
    assert engine.ctx.fold().taught_ids(LC) == set()


def test_a_phase_change_republishes_the_plan_with_teachable(tmp_path: Path) -> None:
    eng, _ = relay_engine(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    subject(eng.ctx, LC, modules=mods)
    fake = FakeRtdb()
    sync = CurriculumSync(wiring(fake, eng))
    node = f"tutor/v1-e2e/subjects/{LC}/plan/modules"

    async def go() -> list[bool]:
        first = await sync.publish(LC)
        grant((LC, "b"))
        fake.log.clear()
        moved = await sync.publish(LC)  # same rev, new phase
        assert [p for _, p in fake.log] == [f"/subjects/{LC}/plan"]
        still = await sync.publish(LC)
        await sync.w.rtdb.aclose()
        return [first, moved, still]

    assert asyncio.run(go()) == [True, True, False]
    assert [m["teachable"] for m in fake.get(node)] == [False, True]


def test_a_newer_published_rev_is_never_overwritten(tmp_path: Path) -> None:
    eng, _ = relay_engine(tmp_path)
    subject(eng.ctx, LC, modules=[module("a", status="ready")])
    fake = FakeRtdb()
    fake.set(f"tutor/v1-e2e/subjects/{LC}/meta/rev", 5)  # ahead of the local 1
    sync = CurriculumSync(wiring(fake, eng))

    async def go() -> bool:
        await sync.startup()
        moved = await sync.publish(LC)
        await sync.w.rtdb.aclose()
        return moved

    assert not asyncio.run(go())
    assert fake.get(f"tutor/v1-e2e/subjects/{LC}/plan") is None
