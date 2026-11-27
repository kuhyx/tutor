# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The study session's turn from the local model while Claude's limit is spent.

:class:`FallbackSession` is a :class:`TutorSession` that keeps its own copy of
the conversation (system prompt, every prompt and reply as text). While a
recorded outage window is open no CLI is spawned; when Claude is or turns
out unavailable, the same turn goes to the local model (``local_model.chat``)
with that history, under the same :data:`TURN_SCHEMA`. Only when the local
model is down too is the outage raised, and the app falls back to the drill.

When Claude is back, its next prompt starts with the turns it missed.
A local turn may teach, ask and grade a check, but never closes a card
(``card_done``), records a mastered concept or edits the deck: those last
for good, and a weak model must not decide them. The learner taps Next to
move on, as with any card the tutor did not close.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Final

from tutor import local_model, outage, research
from tutor.models import TURN_SCHEMA
from tutor.session import Prompt, Reply, TutorSession
from tutor.trace import traced

if TYPE_CHECKING:
    from collections.abc import Callable

    from claude_agent_sdk import ClaudeAgentOptions

    from tutor.trace import Observer

_logger = logging.getLogger(__name__)

# What a local turn may never set, and the value it is forced to.
_KEPT_OUT: Final[dict[str, Any]] = {
    "card_done": False,
    "concepts_mastered": [],
    "card_edits": [],
}
IMAGE_NOTE: Final = "[an image was attached here]"
RECAP: Final = (
    "[Your usage limit was spent for a while; a local model held these turns of"
    " this session. Carry on from them.]"
)

type Chat = Callable[[str, list[dict[str, str]], dict[str, Any]], dict[str, Any] | None]


def as_text(prompt: Prompt) -> str:
    """A prompt as plain text: the local model reads no image blocks."""
    if isinstance(prompt, str):
        return prompt
    parts = [
        str(b.get("text", "")) if b.get("type") == "text" else IMAGE_NOTE
        for b in prompt
    ]
    return "\n\n".join(p for p in parts if p)


class FallbackSession(TutorSession):
    """A tutor session that answers on the local model during an outage."""

    def __init__(
        self,
        options: ClaudeAgentOptions,
        timeout: float = 0.0,
        chat: Chat = local_model.chat,
    ) -> None:
        """Remember the system prompt for the local model; nothing spawns yet."""
        super().__init__(options, timeout)
        prompt = options.system_prompt
        self._system = prompt if isinstance(prompt, str) else json.dumps(prompt)
        self._history: list[dict[str, str]] = []
        self._seen = 0  # history entries Claude has seen (the rest were local)
        self._chat = chat

    async def ask_raw(self, prompt: Prompt, on_trace: Observer | None = None) -> Reply:
        """Claude's reply, or the local model's while Claude is unavailable."""
        text, by_claude = as_text(prompt), True
        try:
            outage.ensure_available(time.time())
            reply = await super().ask_raw(self._caught_up(prompt), on_trace)
        except outage.ClaudeUnavailableError as err:
            _logger.warning("Claude unavailable (%s); the local model answers", err)
            reply, by_claude = await self._local(text, err), False
        said = json.dumps(reply.structured) if reply.structured else reply.text
        self._history += [
            {"role": "user", "content": text},
            {"role": "assistant", "content": said},
        ]
        if by_claude:
            self._seen = len(self._history)
        return reply

    def _caught_up(self, prompt: Prompt) -> Prompt:
        """``prompt`` led by the local turns Claude missed (the limit reset)."""
        missed = self._history[self._seen :]
        if not missed:
            return prompt
        turns = "\n\n".join(f"{m['role']}: {m['content']}" for m in missed)
        recap = f"{RECAP}\n\n{turns}\n\n[The learner's new message follows.]\n\n"
        if isinstance(prompt, str):
            return recap + prompt
        return [{"type": "text", "text": recap}, *prompt]

    async def _local(self, text: str, err: outage.ClaudeUnavailableError) -> Reply:
        """The local model's turn; ``err`` again when it gives none."""
        messages = [*self._history, {"role": "user", "content": text}]
        raw = await asyncio.to_thread(self._chat, self._system, messages, TURN_SCHEMA)
        if raw is None:
            raise err
        raw |= _KEPT_OUT
        init = {"model": local_model.MODEL, "local": True}
        return Reply(raw, json.dumps(raw), init, hook_events=0, cost_usd=0.0)


def tutor_session(system_prompt: str) -> TutorSession:
    """The engine's session: research tools, visible thinking, local fallback."""
    return FallbackSession(traced(research.research_options(system_prompt)))
