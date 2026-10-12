# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The curriculum's model call: isolated options, structured answer, errors."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tutor.curriculum import modelcall
from tutor.curriculum.errors import RequestError
from tutor.session import Reply, SessionError

SCHEMA = {"type": "object"}


class _Session:
    reply: Reply | Exception = Reply({"ok": 1}, "", {}, 0, 0.0)
    closed = 0

    def __init__(self, options: Any) -> None:
        self.options = options

    async def ask_raw(self, prompt: str) -> Reply:
        del prompt
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    async def close(self) -> None:
        type(self).closed += 1


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> type[_Session]:
    monkeypatch.setattr(modelcall, "TutorSession", _Session)
    _Session.closed = 0
    return _Session


def test_options_are_isolated_with_the_schema() -> None:
    opts = modelcall.options("sys", SCHEMA)
    assert opts.tools == []
    assert opts.mcp_servers == {}
    assert opts.setting_sources == []
    assert opts.output_format == {"type": "json_schema", "schema": SCHEMA}


def test_structured_answer(session: type[_Session]) -> None:
    session.reply = Reply({"ok": 1}, "", {}, 0, 0.0)
    assert modelcall.ask_model("s", "p", SCHEMA) == {"ok": 1}
    assert session.closed == 1


def test_text_fallback_and_bad_answers(session: type[_Session]) -> None:
    session.reply = Reply(None, '{"a": 2}', {}, 0, 0.0)
    assert modelcall.ask_model("s", "p", SCHEMA) == {"a": 2}
    for reply in (Reply(None, "not json", {}, 0, 0.0), Reply([1], "", {}, 0, 0.0)):
        session.reply = reply
        with pytest.raises(RequestError) as err:
            modelcall.ask_model("s", "p", SCHEMA)
        assert err.value.code == "model_error"


def test_session_failure_is_model_error(session: type[_Session]) -> None:
    session.reply = SessionError("boom")
    with pytest.raises(RequestError, match="boom") as err:
        modelcall.ask_model("s", "p", SCHEMA)
    assert err.value.code == "model_error"


def test_callable_from_inside_a_running_loop(session: type[_Session]) -> None:
    session.reply = Reply({"ok": 2}, "", {}, 0, 0.0)

    async def inside() -> dict[str, Any]:
        return modelcall.ask_model("s", "p", SCHEMA)

    assert asyncio.run(inside()) == {"ok": 2}
