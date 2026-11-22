#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E scripted model: the sandbox engine's turns come from a file.

``scripts/e2e_sandbox.sh up --scripted`` sets ``TUTOR_E2E_SCRIPT`` to
``<sandbox>/model_script.json``; ``e2e_server.py`` then builds every session
from :class:`ScriptedSession`, never the Claude CLI. A flow writes the queue
(a JSON list) before it sends; each ``ask`` takes the first entry and writes
the rest back. An entry is ``{"message": str, "card_done": bool, "hold":
path}``: ``hold`` waits until that file exists (``HELD`` beside the script
says the model is answering). An empty queue answers :data:`DEFAULT`. Every
prompt is appended to ``<script>.prompts.jsonl`` for the flow to assert on.
The engine, relay and app around it are the real ones.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from claude_agent_sdk import ClaudeAgentOptions

from tutor.models import TutorTurn
from tutor.session import Reply, TutorSession

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.session import Prompt
    from tutor.trace import Observer

ENV: Final = "TUTOR_E2E_SCRIPT"
DEFAULT: Final = "What do you already know about this?"
HOLD_S: Final = 50.0  # a held turn never outlives the flow's 60 s call


def held(script: Path) -> Path:
    """The marker a held turn writes while it waits."""
    return script.with_suffix(".held")


def prompts(script: Path) -> Path:
    """Where every prompt the engine sent is appended."""
    return script.with_suffix(".prompts.jsonl")


def write(script: Path, entries: list[dict[str, Any]]) -> None:
    """Queue ``entries`` (the flow's side); clears a stale held marker."""
    held(script).unlink(missing_ok=True)
    script.write_text(json.dumps(entries), encoding="utf-8")


def _pop(script: Path) -> dict[str, Any]:
    queue = json.loads(script.read_text(encoding="utf-8")) if script.is_file() else []
    if not queue:
        return {"message": DEFAULT}
    script.write_text(json.dumps(queue[1:]), encoding="utf-8")
    return dict(queue[0])


def _wait_for(flag: Path) -> None:
    """Block until ``flag`` exists, at most :data:`HOLD_S`."""
    deadline = time.monotonic() + HOLD_S
    while not flag.exists() and time.monotonic() < deadline:
        time.sleep(0.2)


class ScriptedSession(TutorSession):
    """Answers each ``ask`` with the next queued entry of ``script``."""

    def __init__(self, script: Path) -> None:
        """Nothing is spawned."""
        super().__init__(ClaudeAgentOptions())
        self.script = script

    async def ask(
        self, prompt: Prompt, on_trace: Observer | None = None
    ) -> tuple[TutorTurn, Reply]:
        """The next scripted turn (after its ``hold`` file appears)."""
        del on_trace
        with prompts(self.script).open("a", encoding="utf-8") as log:
            log.write(json.dumps({"at": time.time(), "prompt": str(prompt)}) + "\n")
        entry = _pop(self.script)
        if hold := entry.get("hold"):
            held(self.script).write_text(str(time.time()), encoding="utf-8")
            await asyncio.to_thread(_wait_for, Path(hold))
        turn = TutorTurn(
            message=str(entry["message"]),
            low_effort=False,
            card_done=bool(entry.get("card_done")),
        )
        return turn, Reply(None, turn.message, {}, 0, 0.0)

    async def close(self) -> None:
        """No process to stop."""


def factory(script: Path) -> Callable[[str], TutorSession]:
    """The engine's ``session_factory``: every session reads ``script``."""
    return lambda _prompt: ScriptedSession(script)
