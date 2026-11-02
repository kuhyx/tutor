# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``plan_today`` / ``plan_step_done``: file-backed linear plan."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from tutor import credit
from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import RequestError
from tutor.store import data_dir

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

DEV = "00000000-0000-4000-8000-000000000000"
NOW = 1_800_000_000.0
STEPS = [
    {"id": "a", "title": "A", "what": "w", "kind": "coach", "target": "x"},
    {"id": "b", "title": "B", "what": "w", "kind": "note", "target": ""},
    {"id": "bad", "title": "Bad", "what": "w", "kind": "nope", "target": ""},
]


def _call(kind: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    req = {"kind": kind, "dev": DEV, "created": 1, "body": body or {}}
    ctx = SimpleNamespace(
        now=lambda: NOW, body=protocol.validate("0" * 26, req).body, request=None
    )
    return asyncio.run(CHAT_HANDLERS[kind](cast("RequestContext", ctx)))


def _write(day: str, plan: dict[str, Any]) -> None:
    path = data_dir() / "plan" / f"{day}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan), encoding="utf-8")


def test_no_plan_is_empty() -> None:
    day = credit.local_day(NOW)[0]
    assert _call("plan_today") == {"date": day, "steps": [], "current": None}


def test_current_is_first_undone_and_done_is_idempotent() -> None:
    day = credit.local_day(NOW)[0]
    _write(day, {"steps": STEPS})
    plan = _call("plan_today")
    assert [s["id"] for s in plan["steps"]] == ["a", "b"]  # bad kind dropped
    assert plan["current"] == "a"
    after = _call("plan_step_done", {"id": "a"})
    assert after["current"] == "b"
    assert _call("plan_step_done", {"id": "a"}) == after
    assert _call("plan_step_done", {"id": "b"})["current"] is None


def test_unknown_step_and_bad_id_refused() -> None:
    _write(credit.local_day(NOW)[0], {"steps": STEPS})
    with pytest.raises(RequestError):
        _call("plan_step_done", {"id": "zzz"})
    with pytest.raises(RequestError):
        _call("plan_step_done", {"id": "../x"})


def test_corrupt_file_is_empty() -> None:
    day = credit.local_day(NOW)[0]
    path = data_dir() / "plan" / f"{day}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{nope", encoding="utf-8")
    assert _call("plan_today")["steps"] == []
