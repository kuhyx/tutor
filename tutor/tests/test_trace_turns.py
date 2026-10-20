# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A turn's trace: reported live by the session, kept with the turn, never sent back.

The trace is display only: it is stored with the tutor turn and published,
and must never be fed back to the model (resume primer, prompts).
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from claude_agent_sdk import ClaudeAgentOptions, ThinkingBlock

from tutor import history, resume
from tutor.engine import Engine
from tutor.relay import views
from tutor.session import Reply, TutorSession
from tutor.store import Store
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock, turn
from tutor.tests._trace_support import assistant, delta, tool
from tutor.tests.test_session import RAW_TURN, FakeClient, fake_client, result

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.models import TutorTurn
    from tutor.session import Prompt
    from tutor.trace import Observer

__all__ = ["fake_client"]  # the autouse fixture routes the SDK to FakeClient

SENTINEL = "SENTINEL-REASONING-7f3a"

# -- TutorSession ------------------------------------------------------------------


def test_ask_reports_the_trace_live_and_returns_it(
    fake_client: type[FakeClient],
) -> None:
    fake_client.scripts = [
        [
            delta("Look it "),
            delta("up."),
            assistant(
                ThinkingBlock("Look it up.", "s"), tool("WebSearch", query="relay")
            ),
            assistant(tool("StructuredOutput", **RAW_TURN)),
            result(structured_output=RAW_TURN),
        ]
    ]
    seen: list[list[dict[str, str]]] = []

    async def go() -> tuple[TutorTurn, Reply]:
        session = TutorSession(ClaudeAgentOptions())
        try:
            return await session.ask("hi", on_trace=lambda t: seen.append(t.steps()))
        finally:
            await session.close()

    _, reply = asyncio.run(go())
    want = [
        {"kind": "thinking", "text": "Look it up."},
        {"kind": "tool", "name": "WebSearch", "input": "relay"},
    ]
    assert reply.trace == want
    assert seen == [[want[0] | {"text": "Look it "}], [want[0]], want]


def test_a_reply_without_thinking_has_an_empty_trace(
    fake_client: type[FakeClient],
) -> None:
    fake_client.scripts = [[result(structured_output=RAW_TURN)]]

    async def go() -> Reply:
        session = TutorSession(ClaudeAgentOptions())
        try:
            return (await session.ask("hi"))[1]
        finally:
            await session.close()

    assert asyncio.run(go()).trace == []


# -- the engine stores it; nothing feeds it back -------------------------------------

STEPS = [
    {"kind": "thinking", "text": f"I should ask about coils. {SENTINEL}"},
    {"kind": "tool", "name": "WebSearch", "input": f"relay coil {SENTINEL}"},
]


class TracedSession(FakeSession):
    """A scripted session whose replies carry a trace."""

    async def ask(
        self, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Reply]:
        """The scripted reply, with :data:`STEPS` as its trace."""
        del on_trace
        got, reply = await super().ask(prompt)
        reply.trace = [dict(s) for s in STEPS]
        return got, reply


def _engine(tmp_path: Path, fake: FakeSession) -> Engine:
    return Engine(
        store=Store(tmp_path / "data"),
        now=ManualClock(),
        credit_fn=FakeCredit(),
        session_factory=lambda _prompt: fake,
    )


def test_the_trace_is_stored_with_the_turn_and_never_sent_back(
    tmp_path: Path,
) -> None:
    fake = TracedSession(turn("What does a coil do?"), turn("Good."), turn("Next?"))
    eng = _engine(tmp_path, fake)

    async def go() -> None:
        await eng.start()
        await eng.reply("it makes a magnet")

    asyncio.run(go())
    assert eng.messages[0]["trace"] == STEPS
    path = eng.store.root / "sessions" / f"{eng.session_id}.jsonl"
    logged = [json.loads(line) for line in path.read_text().splitlines()]
    tutor = [e for e in logged if e["type"] == "tutor"]
    assert tutor[0]["ui"]["trace"] == STEPS
    # History replays it; the projection publishes it.
    replayed = resume.replay(path)
    assert replayed is not None
    assert replayed.conversation.messages[0]["trace"] == STEPS
    view = history.View({c.id: c.front for c in eng.deck}, "", set(), set())
    src = views.Sources(view, eng.time(), lambda _r: None, lambda _p: None)
    doc = views.build(eng.store.root / "sessions", eng.session_id, src)
    assert doc is not None
    assert doc.msgs["m0001"]["trace"] == STEPS
    # Never back to the model: not in any prompt, not in the resume primer.
    assert all(SENTINEL not in str(p) for p in fake.prompts)
    assert SENTINEL not in resume.primer(replayed.conversation.messages)


def test_a_turn_without_a_trace_has_no_trace_field(tmp_path: Path) -> None:
    eng = _engine(tmp_path, FakeSession(turn("Hi.")))
    asyncio.run(eng.start())
    assert "trace" not in eng.messages[0]
    view = history.View({c.id: c.front for c in eng.deck}, "", set(), set())
    src = views.Sources(view, eng.time(), lambda _r: None, lambda _p: None)
    doc = views.build(eng.store.root / "sessions", eng.session_id, src)
    assert doc is not None
    assert "trace" not in doc.msgs["m0001"]
