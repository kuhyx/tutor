# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A model sandbox that will not start, seen through ``TutorSession``."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions, ProcessError
import pytest

from tutor import model_fault, session
from tutor.session import SessionError, TutorSession
from tutor.tests.test_model_fault import FENCE, entries
from tutor.tests.test_session import FakeClient, result
from tutor.tests.test_session_task import DeadOnStart

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from tutor.tests.conftest import FaultRig


@pytest.fixture(autouse=True)
def fake_client(monkeypatch: pytest.MonkeyPatch) -> type[FakeClient]:
    """Route the session to the fake client with an empty script."""
    FakeClient.scripts = []
    FakeClient.instances = []
    monkeypatch.setattr(session, "ClaudeSDKClient", FakeClient)
    return FakeClient


def test_the_session_listens_to_the_cli_stderr_and_keeps_the_callers(
    fake_client: type[FakeClient],
) -> None:
    seen: list[str] = []
    fake_client.scripts = [[result(result="ok")]]

    async def go() -> None:
        sess = TutorSession(ClaudeAgentOptions(stderr=seen.append))
        await sess.ask_raw("hi")
        await sess.close()

    asyncio.run(go())
    stderr = fake_client.instances[0].options.stderr
    assert stderr is not None
    stderr("hello")
    assert seen == ["hello"]


class FenceDies(FakeClient):
    """Every CLI process prints the fence line on stderr, then dies."""

    async def receive_response(self) -> AsyncIterator[Any]:
        assert self.options.stderr is not None
        self.options.stderr(FENCE)
        yield None  # an async generator, as the real one is
        msg = "exited"
        raise ProcessError(msg, exit_code=1)


def test_a_cli_that_dies_on_the_fence_files_the_fault_once(
    fault: FaultRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session, "ClaudeSDKClient", FenceDies)

    async def go() -> None:
        sess = TutorSession(ClaudeAgentOptions())
        for _ in range(2):  # the second ask starts a fresh process, fails again
            with pytest.raises(ProcessError):
                await asyncio.wait_for(sess.ask_raw("hi"), 5)
            await asyncio.sleep(0)

    asyncio.run(go())
    assert [e["kind"] for e in entries(fault)] == [model_fault.SANDBOX_KIND]
    assert len(fault.notices) == 1


def test_a_successful_turn_ends_the_streak(
    fault: FaultRig, fake_client: type[FakeClient]
) -> None:
    fault.monitor.stderr_line(FENCE)
    fake_client.scripts = [[result(result="fine")]]

    async def go() -> None:
        sess = TutorSession(ClaudeAgentOptions())
        await sess.ask_raw("hi")
        await sess.close()

    asyncio.run(go())
    fault.monitor.stderr_line(FENCE)
    assert len(fault.notices) == 2


def test_an_error_result_is_filed(
    fault: FaultRig, fake_client: type[FakeClient]
) -> None:
    fake_client.scripts = [[result(is_error=True, subtype="error_during_execution")]]

    async def go() -> None:
        sess = TutorSession(ClaudeAgentOptions())
        try:
            with pytest.raises(SessionError):
                await sess.ask_raw("hi")
        finally:
            await sess.close()

    asyncio.run(go())
    assert [e["kind"] for e in entries(fault)] == [model_fault.ERROR_KIND]


def test_a_cli_that_will_not_start_is_filed(
    fault: FaultRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    DeadOnStart.failures = 1
    monkeypatch.setattr(session, "ClaudeSDKClient", DeadOnStart)

    async def go() -> None:
        sess = TutorSession(ClaudeAgentOptions())
        with pytest.raises(OSError, match="CLI not found"):
            await asyncio.wait_for(sess.ask_raw("one"), 5)

    asyncio.run(go())
    (entry,) = entries(fault)
    assert entry["error"].startswith("OSError:")
