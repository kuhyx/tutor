# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The free-model chat (spec Q8/Q9, part e79be0be-0): ``free_backend``.

While Claude is out, ``session_start`` with ``free`` runs the usual session
on OmniRoute's ``free-best``; its later requests stay free, a gateway
failure is ``free_unavailable`` (never a Claude outage window), and a
Claude start is still refused.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from claude_agent_sdk import ClaudeAgentOptions
import httpx
import pytest

from tutor import backend_mode, free_backend, free_options, outage, unavailable
from tutor.relay.errors import RequestError, classify
from tutor.relay.kinds import kind_of_node
from tutor.tests._fakes import FakeSession, turn
from tutor.tests._relay_support import engine
from tutor.tests.test_relay_lanes import Rig, run

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.session import TutorSession


_KEY = "k-test"


def _key(text: str = "k-1") -> None:
    path = Path.home() / ".config" / "omniroute" / "api_key"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def _gateway(monkeypatch: pytest.MonkeyPatch, answer: Callable[..., Any]) -> None:
    """Every gateway probe answered by ``answer(request)``."""
    monkeypatch.setattr(free_backend, "PROBE_TRANSPORT", httpx.MockTransport(answer))


def _up(monkeypatch: pytest.MonkeyPatch) -> None:
    _key()
    _gateway(monkeypatch, lambda _r: httpx.Response(200, json={"data": []}))


def _free_engine(tmp_path: Path, *replies: Any) -> tuple[Any, list[bool]]:
    """An engine whose sessions note whether they were made on the free backend."""
    eng, fake = engine(tmp_path, *replies)
    seen: list[bool] = []

    def factory(_prompt: str) -> TutorSession:
        seen.append(free_options.applied(ClaudeAgentOptions()).model == "free-best")
        return fake

    eng._factory = factory  # the test's own seam, like _relay_support
    return eng, seen


def test_a_free_chat_runs_while_claude_is_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _up(monkeypatch)
    eng, seen = _free_engine(tmp_path, turn("Q1?"), turn("Q2?"))

    async def script(rig: Rig) -> None:
        now = rig.eng.time()
        unavailable.record("rate_limit", now, now + 900)
        start = {"subject": None, "card": None}
        refused = await rig.send("session_start", start)
        assert refused["code"] == "claude_unavailable"
        got = await rig.send("session_start", {**start, "free": True})
        sid = got["data"]["session"]
        answered = await rig.send("message", {"session": sid, "text": "an answer"})
        assert answered["ok"], answered
        assert free_backend.live(rig.eng)

    run(eng, script)
    assert seen == [True]


def test_a_down_gateway_is_free_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _key()
    _gateway(monkeypatch, lambda _r: httpx.Response(502))
    eng, _ = engine(tmp_path, turn("Q1?"))

    async def script(rig: Rig) -> None:
        body = {"subject": None, "card": None, "free": True}
        got = await rig.send("session_start", body)
        assert (got["code"], got["kind"]) == ("free_unavailable", "outage_free")

    run(eng, script)


def test_a_free_session_failure_records_no_claude_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _up(monkeypatch)
    limit = outage.ClaudeUnavailableError("rate_limit", 1)
    eng, _ = engine(tmp_path, limit)

    async def script(rig: Rig) -> None:
        body = {"subject": None, "card": None, "free": True}
        got = await rig.send("session_start", body)
        assert got["code"] == "free_unavailable"

    run(eng, script)
    assert unavailable.windows() == []


def test_ensure_up_needs_a_key_and_an_ok_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(RequestError, match="no OmniRoute API key"):
        asyncio.run(free_backend.ensure_up())
    _up(monkeypatch)
    asyncio.run(free_backend.ensure_up())

    def refuse(request: httpx.Request) -> httpx.Response:
        msg = "refused"
        raise httpx.ConnectError(msg, request=request)

    _gateway(monkeypatch, refuse)
    with pytest.raises(RequestError, match="ConnectError") as err:
        asyncio.run(free_backend.ensure_up())
    assert classify(err.value).code == "free_unavailable"
    assert kind_of_node("free_unavailable", {}) == "outage_free"


def test_applied_only_inside_a_free_request(monkeypatch: pytest.MonkeyPatch) -> None:
    _key(_KEY)
    base = ClaudeAgentOptions(model="claude-x", env={"KEEP": "1"})
    assert free_options.applied(base) is base
    token = backend_mode.FREE.set(True)
    try:
        got = free_options.applied(base)
        monkeypatch.setenv(free_options.GATEWAY_ENV, "http://127.0.0.1:9")
        dead = free_options.applied(base)
    finally:
        backend_mode.FREE.reset(token)
    assert got.model == free_options.MODEL
    assert got.env["KEEP"] == "1"
    assert got.env["ANTHROPIC_AUTH_TOKEN"] == _KEY
    assert got.env["ANTHROPIC_BASE_URL"] == free_options.DEFAULT_GATEWAY
    assert got.env["TUTOR_MODEL_GATEWAY_PORT"] == "20128"
    assert dead.env["TUTOR_MODEL_GATEWAY_PORT"] == "9"
    monkeypatch.setenv(free_options.GATEWAY_ENV, "http://gateway.invalid")
    token = backend_mode.FREE.set(True)
    try:
        assert free_options.applied(base).env["TUTOR_MODEL_GATEWAY_PORT"] == "80"
    finally:
        backend_mode.FREE.reset(token)


def test_record_writes_no_window_in_a_free_request() -> None:
    token = backend_mode.FREE.set(True)
    try:
        err = outage.record(outage.ClaudeUnavailableError("overloaded"), now=100.0)
    finally:
        backend_mode.FREE.reset(token)
    assert err.reason == "overloaded"
    assert unavailable.windows() == []


def test_live_is_false_before_any_session(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path, turn("Q?"))
    assert not free_backend.live(eng)
    assert isinstance(FakeSession(), FakeSession)
