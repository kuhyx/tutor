# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Claude outages: detected from typed SDK fields, retried once, recorded."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    RateLimitEvent,
    RateLimitInfo,
    ResultError,
)
import pytest

from tutor import outage, session, unavailable
from tutor.outage import ClaudeUnavailableError
from tutor.session import TutorSession
from tutor.tests.test_session import RAW_TURN, FakeClient, result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from claude_agent_sdk.types import AssistantMessageError, RateLimitStatus


def limited(
    status: RateLimitStatus = "rejected", resets_at: int | None = 5000
) -> RateLimitEvent:
    """A rate limit event."""
    info = RateLimitInfo(status=status, resets_at=resets_at)
    return RateLimitEvent(rate_limit_info=info, uuid="u", session_id="s")


def said(error: AssistantMessageError | None) -> AssistantMessage:
    """An assistant message carrying the CLI's error kind."""
    return AssistantMessage(content=[], model="m", error=error)


def failed(status: int | None = None, terminal: str | None = None) -> Any:
    """An API-error result (the CLI's ``success`` + ``is_error``)."""
    return result(is_error=True, api_error_status=status, terminal_reason=terminal)


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        ([limited(), failed(429)], ("rate_limit", 5000)),
        ([limited(resets_at=None), said("rate_limit")], ("rate_limit", None)),
        ([said("rate_limit"), failed(429)], ("rate_limit", None)),
        ([failed(529)], ("overloaded", None)),
        ([said("server_error"), failed(503)], ("overloaded", None)),
        ([said("server_error"), failed()], ("network", None)),
        ([failed(terminal="api_error")], ("network", None)),
    ],
)
def test_outages_are_named_from_fields(
    messages: list[Any], expected: tuple[str, int | None]
) -> None:
    found = outage.detect(messages)
    assert found is not None
    assert (found.reason, found.resets_at) == expected


@pytest.mark.parametrize(
    "messages",
    [
        [limited(), result()],  # it answered: overage served it
        [limited("allowed_warning"), said(None), result()],
        [said("invalid_request"), failed(400)],
        [failed(terminal="max_turns")],
        [],
    ],
)
def test_not_an_outage(messages: list[Any]) -> None:
    assert outage.detect(messages) is None


def test_record_writes_the_window_and_says_when_it_ends() -> None:
    err = outage.record(ClaudeUnavailableError("network"), now=1000)
    assert err.resets_at == 1000 + unavailable.DEFAULT_SPAN
    assert err.fields() == {"reason": "network", "resets_at": err.resets_at}
    assert str(err) == f"Claude is unavailable (network) until {err.resets_at}"
    assert unavailable.windows() == [unavailable.Window(1000, err.resets_at, "network")]
    assert (
        str(ClaudeUnavailableError("overloaded"))
        == "Claude is unavailable (overloaded)"
    )


def test_from_exit_maps_only_api_outages() -> None:
    other = RuntimeError("x")
    assert outage.from_exit(other) is other
    assert outage.from_exit(None) is None
    bad_request = ResultError("e", {"api_error_status": 400})
    assert outage.from_exit(bad_request) is bad_request
    down = outage.from_exit(ResultError("e", {"api_error_status": 529}))
    assert isinstance(down, ClaudeUnavailableError)
    assert down.reason == "overloaded"
    assert [w.reason for w in unavailable.windows()] == ["overloaded"]


def _script(*outcomes: Any) -> tuple[Callable[[], Awaitable[str]], list[int]]:
    calls: list[int] = []

    async def turn() -> str:
        calls.append(1)
        item = outcomes[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return str(item)

    return turn, calls


def test_overloaded_is_retried_exactly_once() -> None:
    turn, calls = _script(ClaudeUnavailableError("overloaded"), "ok")
    assert asyncio.run(outage.retrying(turn)) == "ok"
    assert len(calls) == 2
    assert unavailable.windows() == []
    turn, calls = _script(*[ClaudeUnavailableError("network")] * 2)
    with pytest.raises(ClaudeUnavailableError) as err:
        asyncio.run(outage.retrying(turn))
    assert len(calls) == 2
    assert err.value.resets_at is not None
    assert [w.reason for w in unavailable.windows()] == ["network"]


def test_a_rate_limit_is_not_retried() -> None:
    turn, calls = _script(ClaudeUnavailableError("rate_limit", 9_999_999_999))
    with pytest.raises(ClaudeUnavailableError) as err:
        asyncio.run(outage.retrying(turn))
    assert len(calls) == 1
    assert err.value.resets_at == 9_999_999_999


def test_ensure_available_fails_fast_inside_a_window() -> None:
    outage.ensure_available(100.0)
    unavailable.record("rate_limit", 100, resets_at=200)
    with pytest.raises(ClaudeUnavailableError) as err:
        outage.ensure_available(150.0)
    assert err.value.fields() == {"reason": "rate_limit", "resets_at": 200}
    outage.ensure_available(200.0)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> type[FakeClient]:
    """Route the session to the fake client."""
    FakeClient.scripts = []
    FakeClient.instances = []
    monkeypatch.setattr(session, "ClaudeSDKClient", FakeClient)
    return FakeClient


async def _two_asks(sess: TutorSession) -> list[Any]:
    out: list[Any] = []
    for _ in range(2):  # one at a time: the second must reuse the same process
        out += await asyncio.gather(sess.ask("hi"), return_exceptions=True)
    await sess.close()
    return out


def test_session_retries_once_then_relays_and_keeps_the_process(
    client: type[FakeClient],
) -> None:
    client.scripts = [
        [said("server_error"), failed(529)],
        [said("server_error"), failed(529)],
        [limited(resets_at=9_999_999_999), failed(429)],
        [result(structured_output=RAW_TURN)],
    ]
    first, second = asyncio.run(_two_asks(TutorSession(ClaudeAgentOptions())))
    assert isinstance(first, ClaudeUnavailableError)
    assert first.reason == "overloaded"
    assert isinstance(second, ClaudeUnavailableError)
    assert (second.reason, second.resets_at) == ("rate_limit", 9_999_999_999)
    assert len(client.instances) == 1  # one CLI process throughout
    assert client.instances[0].prompts == ["hi", "hi", "hi"]
    assert [w.reason for w in unavailable.windows()] == ["overloaded", "rate_limit"]
