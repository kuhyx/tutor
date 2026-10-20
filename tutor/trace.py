# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What the model thought and did during one turn (display only).

kuhy wants to watch the tutor think and research, live and afterwards. The
SDK streams summarized thinking as ``thinking_delta`` events (with
``include_partial_messages``) and reports each tool call as a
``ToolUseBlock``; :class:`Trace` turns them into ordered steps:
``{"kind": "thinking", "text"}`` and ``{"kind": "tool", "name", "input"}``.

The trace is stored with the tutor turn (``ui.trace``) and published; it is
NEVER fed back to the model (the resume primer reads text and questions only).
The reply's draft text is not traced: the image check may rewrite it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final

from claude_agent_sdk import AssistantMessage, StreamEvent, ThinkingBlock, ToolUseBlock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable

    from claude_agent_sdk import ClaudeAgentOptions

    from tutor.session import Effort

# Caps keep a tutor message under the contract's 24 KB (DOCS-contract §9).
THINKING_CAP: Final = 8000
TOOLS_CAP: Final = 30
INPUT_CAP: Final = 150
# How the CLI hands back the structured turn: the output, not research.
_HIDDEN_TOOLS: Final = frozenset({"StructuredOutput"})
# The one input that says what a tool call is about.
_INPUT_KEYS: Final = {
    "WebSearch": "query",
    "WebFetch": "url",
    "Bash": "command",
    "Read": "file_path",
    "Grep": "pattern",
    "Glob": "pattern",
}
_BREAK: Final = "\n\n"
_ELLIPSIS: Final = "…"
# Medium effort produced no thinking at all on the tutor prompt (probe of
# 2026-10-20: 0 thinking deltas at medium, 17 at high), so tutor turns run high.
TUTOR_EFFORT: Final[Effort] = "high"


def summary(name: str, args: dict[str, Any]) -> str:
    """The input worth showing for one tool call: one line, at most the cap."""
    value = args.get(_INPUT_KEYS.get(name, ""))
    if not isinstance(value, str):
        value = next((v for v in args.values() if isinstance(v, str)), "")
    line = " ".join(value.split())
    if len(line) > INPUT_CAP:
        line = line[: INPUT_CAP - 1] + _ELLIPSIS
    return line


def coalesce(chunks: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Chunks as steps: adjacent thinking chunks joined into one."""
    steps: list[dict[str, str]] = []
    for chunk in chunks:
        if chunk["kind"] == "thinking" and steps and steps[-1]["kind"] == "thinking":
            steps[-1] = {**steps[-1], "text": steps[-1]["text"] + chunk["text"]}
        else:
            steps.append(dict(chunk))
    return steps


@dataclass
class Trace:
    """One turn's thinking and tool calls, as append-only chunks."""

    chunks: list[dict[str, str]] = field(default_factory=list)
    _thinking: int = 0  # thinking characters kept (the cap counts these)
    _streamed: bool = False  # deltas seen: whole ThinkingBlocks repeat them
    _tools: int = 0

    def steps(self) -> list[dict[str, str]]:
        """The steps so far, in order."""
        return coalesce(self.chunks)

    def feed(self, msg: object) -> bool:
        """Take one SDK message; ``True`` when the trace changed."""
        if getattr(msg, "parent_tool_use_id", None):
            return False  # a subagent's own stream
        if isinstance(msg, StreamEvent):
            return self._event(msg.event)
        if isinstance(msg, AssistantMessage):
            changed = [self._block(b) for b in msg.content]
            return any(changed)
        return False

    def _event(self, event: dict[str, Any]) -> bool:
        kind = event.get("type")
        if kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "thinking" and self._last_is_thinking():
                return self._think(_BREAK)
            return False
        delta = event.get("delta") or {}
        if kind == "content_block_delta" and delta.get("type") == "thinking_delta":
            self._streamed = True
            return self._think(str(delta.get("thinking", "")))
        return False

    def _block(self, block: object) -> bool:
        if isinstance(block, ThinkingBlock):
            if self._streamed or not block.thinking:
                return False
            lead = _BREAK if self._last_is_thinking() else ""
            return self._think(lead + block.thinking)
        if isinstance(block, ToolUseBlock) and block.name not in _HIDDEN_TOOLS:
            if self._tools >= TOOLS_CAP:
                return False
            self._tools += 1
            step = {"kind": "tool", "name": block.name}
            self.chunks.append(step | {"input": summary(block.name, block.input)})
            return True
        return False

    def _last_is_thinking(self) -> bool:
        return bool(self.chunks) and self.chunks[-1]["kind"] == "thinking"

    def _think(self, text: str) -> bool:
        room = THINKING_CAP - self._thinking
        if not text or room <= 0:
            return False
        if len(text) > room:
            text = text[:room] + _ELLIPSIS
            self._thinking = THINKING_CAP  # nothing more is kept
        else:
            self._thinking += len(text)
        self.chunks.append({"kind": "thinking", "text": text})
        return True


type Observer = Callable[[Trace], None]


async def read_turn(
    stream: AsyncIterator[Any], on_trace: Observer | None = None
) -> tuple[list[Any], list[dict[str, str]]]:
    """Read one turn's messages and its trace's steps.

    ``on_trace`` sees the :class:`Trace` each time it grows. It runs inside
    the SDK read loop, so it must only record (no I/O, never block).
    """
    trace, msgs = Trace(), []
    async for msg in stream:
        msgs.append(msg)
        if trace.feed(msg) and on_trace is not None:
            on_trace(trace)
    return msgs, trace.steps()


def traced(options: ClaudeAgentOptions) -> ClaudeAgentOptions:
    """``options`` for a tutor turn whose thinking is visible and streamed."""
    return replace(
        options,
        thinking={"type": "adaptive", "display": "summarized"},
        include_partial_messages=True,
        effort=TUTOR_EFFORT,
    )
