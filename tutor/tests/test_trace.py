# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The model's thinking and tool calls as ordered, capped steps (``tutor.trace``)."""

from __future__ import annotations

from claude_agent_sdk import (
    ClaudeAgentOptions,
    StreamEvent,
    TextBlock,
    ThinkingBlock,
)

from tutor import trace
from tutor.tests._trace_support import assistant, delta, started, tool
from tutor.tests.test_session import result
from tutor.trace import Trace


def test_streamed_thinking_and_tool_calls_become_ordered_steps() -> None:
    t = Trace()
    msgs = [
        started("thinking"),
        delta("Check what "),
        delta("Modbus does."),
        assistant(
            ThinkingBlock("Check what Modbus does.", "sig"),
            tool("WebSearch", query="modbus function codes"),
        ),
        started("thinking"),
        delta("Now fetch it."),
        assistant(
            ThinkingBlock("Now fetch it.", "sig"),
            tool("WebFetch", url="https://example.org/modbus", prompt="codes"),
            tool("Bash", command="ls -la /tmp", description="list"),
            tool("StructuredOutput", message="x"),
            TextBlock(""),
        ),
    ]
    changed = [t.feed(m) for m in msgs]
    assert t.steps() == [
        {"kind": "thinking", "text": "Check what Modbus does."},
        {"kind": "tool", "name": "WebSearch", "input": "modbus function codes"},
        {"kind": "thinking", "text": "Now fetch it."},
        {"kind": "tool", "name": "WebFetch", "input": "https://example.org/modbus"},
        {"kind": "tool", "name": "Bash", "input": "ls -la /tmp"},
    ]
    # The final ThinkingBlocks repeat streamed text: no change, no duplicate.
    assert changed == [False, True, True, True, False, True, True]


def test_unstreamed_thinking_blocks_are_used() -> None:
    t = Trace()
    t.feed(assistant(ThinkingBlock("First idea.", "s"), tool("Grep", pattern="x")))
    t.feed(assistant(ThinkingBlock("Second.", "s")))
    t.feed(assistant(ThinkingBlock("Third.", "s")))
    assert t.steps() == [
        {"kind": "thinking", "text": "First idea."},
        {"kind": "tool", "name": "Grep", "input": "x"},
        {"kind": "thinking", "text": "Second.\n\nThird."},
    ]


def test_subagent_messages_and_other_events_are_ignored() -> None:
    t = Trace()
    sub = StreamEvent(
        uuid="u",
        session_id="s",
        event=delta("x").event,
        parent_tool_use_id="parent",
    )
    text = StreamEvent(
        uuid="u",
        session_id="s",
        event={"type": "content_block_delta", "delta": {"type": "text_delta"}},
    )
    assert not t.feed(sub)
    assert not t.feed(text)
    assert not t.feed(result())
    assert not t.feed(assistant(tool("StructuredOutput", message="hi")))
    assert t.steps() == []


def test_tool_inputs_are_one_short_line() -> None:
    long = "word " * 100
    assert trace.summary("Bash", {"command": "echo  a\n  b"}) == "echo a b"
    got = trace.summary("WebSearch", {"query": long})
    assert len(got) == trace.INPUT_CAP
    assert got.endswith("…")
    assert trace.summary("Mystery", {"n": 3, "path": "/etc/x"}) == "/etc/x"
    assert trace.summary("Mystery", {"n": 3}) == ""


def test_thinking_and_tool_caps() -> None:
    t = Trace()
    t.feed(delta("a" * (trace.THINKING_CAP - 5)))
    t.feed(delta("b" * 50))
    t.feed(delta("c" * 50))
    for n in range(trace.TOOLS_CAP + 5):
        t.feed(assistant(tool("WebSearch", query=f"q{n}")))
    steps = t.steps()
    text = steps[0]["text"]
    assert text == "a" * (trace.THINKING_CAP - 5) + "bbbbb…"
    assert sum(s["kind"] == "tool" for s in steps) == trace.TOOLS_CAP


def test_traced_options_ask_for_visible_thinking() -> None:
    base = ClaudeAgentOptions(model="m", effort="medium")
    opts = trace.traced(base)
    assert opts.thinking == {"type": "adaptive", "display": "summarized"}
    assert opts.include_partial_messages is True
    # Medium effort produced no thinking at all on the tutor prompt (probe,
    # 2026-10-20); high does.
    assert opts.effort == "high"
    assert opts.model == "m"
    assert base.include_partial_messages is False  # a copy, not a mutation


def test_a_second_streamed_thinking_block_starts_a_paragraph() -> None:
    t = Trace()
    t.feed(delta("One."))
    assert t.feed(started("thinking"))
    t.feed(delta("Two."))
    assert t.steps() == [{"kind": "thinking", "text": "One.\n\nTwo."}]
