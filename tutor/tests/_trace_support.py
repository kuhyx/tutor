# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""SDK messages for the trace tests: thinking deltas, blocks, tool calls."""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import AssistantMessage, StreamEvent, ToolUseBlock


def delta(text: str) -> StreamEvent:
    """A streamed thinking delta, as ``include_partial_messages`` sends it."""
    event = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "thinking_delta", "thinking": text},
    }
    return StreamEvent(uuid="u", session_id="s", event=event)


def started(kind: str) -> StreamEvent:
    """A content block starting."""
    event = {"type": "content_block_start", "index": 0, "content_block": {"type": kind}}
    return StreamEvent(uuid="u", session_id="s", event=event)


def assistant(*blocks: Any) -> AssistantMessage:
    """A finished assistant message."""
    return AssistantMessage(content=list(blocks), model="m")


def tool(name: str, **args: Any) -> ToolUseBlock:
    """A tool call block."""
    return ToolUseBlock(id=f"t-{name}", name=name, input=args)


def search(query: str) -> AssistantMessage:
    """The model calling WebSearch."""
    return assistant(tool("WebSearch", query=query))
