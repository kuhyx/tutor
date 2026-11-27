# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A spent Claude limit: the study session answers on the local model."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions
import pytest

from tutor import local_model, local_session, unavailable
from tutor.local_session import FallbackSession, as_text
from tutor.outage import ClaudeUnavailableError
from tutor.session import Prompt, Reply, TutorSession
from tutor.store import data_dir
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.trace import Observer


def _turn(message: str, **fields: Any) -> dict[str, Any]:
    """A raw turn as the model writes it."""
    raw: dict[str, Any] = {
        "message": message,
        "questions": [message],
        "low_effort": False,
        "check": None,
        "check_result": None,
        "images": [],
        "diagram": None,
        "concepts_mastered": [],
        "card_done": False,
        "choices": [],
        "card_edits": [],
    }
    return raw | fields


class Claude:
    """What the CLI answers under :class:`FallbackSession` (patched ``ask_raw``)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *items: Any) -> None:
        self.items = list(items)
        self.prompts: list[Prompt] = []
        claude = self

        async def ask_raw(
            self: TutorSession, prompt: Prompt, on_trace: Observer | None = None
        ) -> Reply:
            del self, on_trace
            claude.prompts.append(prompt)
            item = claude.items.pop(0)
            if isinstance(item, Exception):
                raise item
            return Reply(item, "", {"model": "claude"}, 0, 0.1)

        monkeypatch.setattr(TutorSession, "ask_raw", ask_raw)


class Local:
    """The local model: scripted answers; ``None`` is "Ollama is down"."""

    def __init__(self, *answers: dict[str, Any] | None) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    def __call__(
        self, system: str, messages: list[dict[str, str]], schema: dict[str, Any]
    ) -> dict[str, Any] | None:
        del schema
        self.calls.append((system, messages))
        return self.answers.pop(0)


def _session(local: Local) -> FallbackSession:
    return FallbackSession(ClaudeAgentOptions(system_prompt="SYS"), chat=local)


def test_as_text_keeps_text_and_marks_images() -> None:
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": "look"},
        {"type": "image", "source": {}},
        {"type": "text", "text": ""},
    ]
    assert as_text(blocks) == f"look\n\n{local_session.IMAGE_NOTE}"
    assert as_text("plain") == "plain"


def test_a_429_mid_session_goes_local_with_the_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude answers turn 1; turn 2 hits the limit and the local model has turn 1."""
    claude = Claude(monkeypatch, _turn("Q1?"), ClaudeUnavailableError("rate_limit"))
    local = Local(_turn("Local Q2?", card_done=True, concepts_mastered=["coil"]))
    session = _session(local)
    first, _ = asyncio.run(session.ask("start"))
    second, reply = asyncio.run(session.ask("my answer"))
    assert (first.message, second.message) == ("Q1?", "Local Q2?")
    assert second.card_done is False  # a local turn never closes a card
    assert second.concepts_mastered == ()
    assert reply.init == {"model": local_model.MODEL, "local": True}
    system, messages = local.calls[0]
    assert system == "SYS"
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert "Q1?" in messages[1]["content"]
    assert messages[2]["content"] == "my answer"
    assert len(claude.prompts) == 2


def test_claude_back_from_the_limit_sees_the_local_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude, a 429, a local turn, a second local turn, then Claude again."""
    claude = Claude(
        monkeypatch,
        _turn("Q1?"),
        ClaudeUnavailableError("rate_limit"),
        _turn("Q4?"),
        _turn("Q5?"),
        _turn("Q7?"),
    )
    local = Local(_turn("Local Q2?"), _turn("Local Q3?"), _turn("Local Q6?"))
    session = _session(local)
    asyncio.run(session.ask("start"))
    asyncio.run(session.ask("answer 2"))
    unavailable.record("rate_limit", 0, 4e9)
    asyncio.run(session.ask("answer 3"))  # the window: no CLI at all
    (data_dir() / "unavailable.jsonl").unlink()
    image = {"type": "image", "source": {}}
    asyncio.run(session.ask([{"type": "text", "text": "answer 4"}, image]))
    asyncio.run(session.ask("answer 5"))
    back = claude.prompts[2]
    assert isinstance(back, list)
    recap = back[0]["text"]
    assert recap.startswith(local_session.RECAP)
    for said in ("answer 2", "Local Q2?", "answer 3", "Local Q3?"):
        assert said in recap
    assert "Q1?" not in recap  # Claude answered that one itself
    assert back[1:] == [{"type": "text", "text": "answer 4"}, image]
    assert claude.prompts[3] == "answer 5"  # caught up: nothing to repeat
    unavailable.record("rate_limit", 0, 4e9)
    asyncio.run(session.ask("answer 6"))
    (data_dir() / "unavailable.jsonl").unlink()
    asyncio.run(session.ask("answer 7"))
    text = claude.prompts[4]
    assert isinstance(text, str)
    assert text.startswith(local_session.RECAP)
    assert "Local Q6?" in text
    assert text.endswith("answer 7")
    assert "Local Q2?" not in text


def test_an_open_window_spawns_no_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    claude = Claude(monkeypatch)
    unavailable.record("rate_limit", 0, 4e9)
    turn, _ = asyncio.run(_session(Local(_turn("Local?"))).ask("start"))
    assert turn.message == "Local?"
    assert claude.prompts == []


def test_the_outage_stands_when_the_local_model_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Claude(monkeypatch, ClaudeUnavailableError("overloaded", 99))
    with pytest.raises(ClaudeUnavailableError) as err:
        asyncio.run(_session(Local(None)).ask("start"))
    assert (err.value.reason, err.value.resets_at) == ("overloaded", 99)


def test_text_reply_is_remembered_as_text(monkeypatch: pytest.MonkeyPatch) -> None:
    Claude(monkeypatch, None, ClaudeUnavailableError("network"))
    local = Local(_turn("Local?"))
    session = _session(local)
    asyncio.run(session.ask_raw("hi"))
    asyncio.run(session.ask_raw("again"))
    assert local.calls[0][1][1] == {"role": "assistant", "content": ""}


def test_tutor_session_is_the_fallback_on_research_options(tmp_path: Path) -> None:
    del tmp_path  # the conftest's data dir holds the sandbox
    session = local_session.tutor_session("SYS")
    assert isinstance(session, FallbackSession)


def test_chat_kinds_answer_locally_while_claude_is_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Over the relay: start, message, next and resume all work in an outage."""
    claude = Claude(monkeypatch)
    monkeypatch.setattr(local_model, "ready", lambda: True)
    local = Local(*(_turn(f"Local {n}?") for n in range(5)))
    eng, _ = engine(tmp_path, factory=lambda prompt: _session(local))

    async def script(rig: Rig) -> None:
        # Real time (the session's check) through the engine's clock (the gate's).
        unavailable.record("rate_limit", time.time(), rig.eng.time() + 900)
        got = await rig.send("session_start", {"subject": None, "card": None})
        assert got["ok"], got
        sid = got["data"]["session"]
        for kind, body in (
            ("message", {"session": sid, "text": "an answer"}),
            ("session_resume", {"session": sid}),
            ("next", {"session": sid}),
        ):
            got = await rig.send(kind, body)
            assert got["ok"], (kind, got)

    run(eng, script)
    assert claude.prompts == []
    assert len(local.calls) >= 3
