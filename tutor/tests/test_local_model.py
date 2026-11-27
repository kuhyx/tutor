# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The local model (Ollama) for replies Claude cannot give while its limit is spent."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tutor import local_model, outage
from tutor.curriculum import modelcall
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, MODEL_ERROR, RequestError
from tutor.outage import ClaudeUnavailableError


def _never(*_args: object, **_kwargs: object) -> dict[str, Any]:
    """Stands in for a call that must not happen."""
    msg = "never called"
    raise AssertionError(msg)


def test_ask_returns_structured_answer() -> None:
    """ask returns the parsed JSON when the local model answers correctly."""

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["format"] == {"type": "object"}
        assert payload["stream"] is False
        return {"message": {"content": '{"reply_md": "hi"}'}}

    result = local_model.ask("sys", "prompt", {"type": "object"}, post=fake_post)
    assert result == {"reply_md": "hi"}


def test_ask_returns_none_on_network_error() -> None:
    """ask returns None when the POST fails with a connection error."""

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        msg = "down"
        raise httpx.ConnectError(msg)

    result = local_model.ask("sys", "prompt", {"type": "object"}, post=fake_post)
    assert result is None


def test_ask_returns_none_on_invalid_json() -> None:
    """ask returns None when the model returns invalid JSON."""

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        return {"message": {"content": "not json"}}

    result = local_model.ask("sys", "prompt", {"type": "object"}, post=fake_post)
    assert result is None


def test_ask_returns_none_on_non_object_json() -> None:
    """ask returns None when the model returns a non-object JSON (e.g. an array)."""

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        return {"message": {"content": "[1]"}}

    result = local_model.ask("sys", "prompt", {"type": "object"}, post=fake_post)
    assert result is None


def test_post_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """_post returns the JSON body from the response."""

    class FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, Any]:
            return {"x": 1}

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> FakeResponse:
        assert json == {}
        return FakeResponse()

    monkeypatch.setattr(local_model.httpx, "post", fake_post)
    result = local_model._post({})
    assert result == {"x": 1}


def test_ask_or_local_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """ask_or_local returns ask_model's answer when Claude is available."""

    monkeypatch.setattr(modelcall, "ask_model", lambda *a, **k: {"a": 1})
    monkeypatch.setattr(outage, "ensure_available", lambda *a, **k: None)
    calls = []

    def local_should_not_be_called(*args: Any, **kwargs: Any) -> None:
        calls.append(1)
        msg = "local model must not be called when Claude answers"
        raise AssertionError(msg)

    monkeypatch.setattr(local_model, "ask", local_should_not_be_called)
    result = modelcall.ask_or_local("sys", "prompt", {"type": "object"})
    assert result == ({"a": 1}, None)
    assert not calls


def test_ask_or_local_claude_unavailable_local_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask_or_local falls back to the local model when ask_model raises CLAUDE_UNAVAILABLE."""

    def ask_model_raises(*args: Any, **kwargs: Any) -> dict[str, Any]:
        msg = "limit"
        raise RequestError(CLAUDE_UNAVAILABLE, msg)

    monkeypatch.setattr(modelcall, "ask_model", ask_model_raises)
    monkeypatch.setattr(outage, "ensure_available", lambda *a, **k: None)
    monkeypatch.setattr(local_model, "ask", lambda *a, **k: {"b": 2})
    result = modelcall.ask_or_local("sys", "prompt", {"type": "object"})
    assert result == ({"b": 2}, local_model.MODEL)


def test_ask_or_local_window_open_local_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask_or_local falls back to the local model when ensure_available raises."""

    def ensure_raises(*args: Any, **kwargs: Any) -> None:
        msg = "rate_limit"
        raise ClaudeUnavailableError(msg)

    monkeypatch.setattr(outage, "ensure_available", ensure_raises)
    monkeypatch.setattr(modelcall, "ask_model", _never)
    monkeypatch.setattr(local_model, "ask", lambda *a, **k: {"c": 3})
    result = modelcall.ask_or_local("sys", "prompt", {"type": "object"})
    assert result == ({"c": 3}, local_model.MODEL)


def test_ask_or_local_both_down_raises_claude_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask_or_local raises RequestError(CLAUDE_UNAVAILABLE) when both Claude and local are down."""

    def ask_model_raises(*args: Any, **kwargs: Any) -> dict[str, Any]:
        msg = "limit"
        raise RequestError(CLAUDE_UNAVAILABLE, msg)

    monkeypatch.setattr(modelcall, "ask_model", ask_model_raises)
    monkeypatch.setattr(outage, "ensure_available", lambda *a, **k: None)
    monkeypatch.setattr(local_model, "ask", lambda *a, **k: None)
    with pytest.raises(RequestError) as exc:
        modelcall.ask_or_local("sys", "prompt", {"type": "object"})
    assert exc.value.code == CLAUDE_UNAVAILABLE


def test_ask_or_local_window_open_local_down_raises_claude_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask_or_local raises ClaudeUnavailableError when ensure_available fails and local returns None."""

    def ensure_raises(*args: Any, **kwargs: Any) -> None:
        msg = "rate_limit"
        raise ClaudeUnavailableError(msg)

    monkeypatch.setattr(outage, "ensure_available", ensure_raises)
    monkeypatch.setattr(modelcall, "ask_model", _never)
    monkeypatch.setattr(local_model, "ask", lambda *a, **k: None)
    with pytest.raises(ClaudeUnavailableError):
        modelcall.ask_or_local("sys", "prompt", {"type": "object"})


def test_ask_or_local_other_errors_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask_or_local does not swallow non-CLAUDE_UNAVAILABLE errors."""

    def ask_model_raises(*args: Any, **kwargs: Any) -> dict[str, Any]:
        msg = "bad"
        raise RequestError(MODEL_ERROR, msg)

    monkeypatch.setattr(modelcall, "ask_model", ask_model_raises)
    monkeypatch.setattr(outage, "ensure_available", lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(local_model, "ask", lambda *a, **k: calls.append(1))
    with pytest.raises(RequestError) as exc:
        modelcall.ask_or_local("sys", "prompt", {"type": "object"})
    assert exc.value.code == MODEL_ERROR
    assert not calls


class _Tags:
    """A fake ``/api/tags`` response."""

    def __init__(self, body: object) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        """Always fine."""

    def json(self) -> object:
        return self.body


def test_ready_needs_the_model_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    listed = {"models": [{"name": local_model.MODEL}]}
    monkeypatch.setattr(local_model.httpx, "get", lambda *_a, **_k: _Tags(listed))
    assert local_model.ready() is True
    other = {"models": [{"name": "llama3.2:latest"}]}
    monkeypatch.setattr(local_model.httpx, "get", lambda *_a, **_k: _Tags(other))
    assert local_model.ready() is False
    monkeypatch.setattr(local_model.httpx, "get", lambda *_a, **_k: _Tags([1]))
    assert local_model.ready() is False


def test_ready_is_false_when_ollama_is_down() -> None:
    """The conftest blocks the network: the probe fails closed."""
    assert local_model.ready() is False


def test_chat_sends_the_history_with_context_and_keep_alive() -> None:
    sent: list[dict[str, Any]] = []

    def fake_post(payload: dict[str, Any]) -> dict[str, Any]:
        sent.append(payload)
        return {"message": {"content": '{"message": "ok"}'}}

    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    got = local_model.chat("SYS", history, {"type": "object"}, post=fake_post)
    assert got == {"message": "ok"}
    payload = sent[0]
    assert payload["messages"] == [{"role": "system", "content": "SYS"}, *history]
    assert payload["options"] == {"num_ctx": local_model.NUM_CTX}
    assert payload["keep_alive"] == local_model.KEEP_ALIVE
