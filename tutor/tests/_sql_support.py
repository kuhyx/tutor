# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the SQL relay tests: ctx, calls, a fake ``sql_drills``."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from tutor import focus_hook
from tutor.relay import protocol, sql
from tutor.relay.chat import CHAT_HANDLERS
from tutor.tests._fake_fp import FakeFp

if TYPE_CHECKING:
    import pytest

    from tutor.relay.context import RequestContext

RID = "01J00000000000000000000000"
DEV = "00000000-0000-4000-8000-000000000000"
NOW = 1_800_000_000.0
META = {
    "id": "q1",
    "title": "Null trap",
    "topic": "basics",
    "kind": "write",
    "source": "builtin",
}


class UnknownDrillError(KeyError):
    """Like ``sql_drills``' error for an id it does not have."""


class EngineError(RuntimeError):
    """Like ``sql_drills``' Docker failure."""


@dataclass(frozen=True)
class Meta:
    """A ``DrillMeta`` as a dataclass (the real package returns those)."""

    id: str
    title: str
    topic: str
    kind: str
    source: str


@dataclass
class FakeSd:
    """Records every call; ``boom`` is raised by the engine calls."""

    calls: list[tuple[str, Any]] = field(default_factory=list)
    boom: Exception | None = None
    saved: list[dict[str, str]] = field(default_factory=list)
    save_errors: list[Exception] = field(default_factory=list)
    run_result: dict[str, Any] = field(
        default_factory=lambda: {"ok": True, "match": True, "rows": [["1"]]}
    )

    def _hit(self, name: str, arg: Any = None) -> None:
        self.calls.append((name, arg))
        if self.boom is not None:
            raise self.boom

    def ensure_running(self) -> None:
        self._hit("ensure_running")

    def list_drills(self) -> list[Meta]:
        self._hit("list_drills")
        return [Meta(**META), Meta("g1", "Mine", "pivot", "write", "generated")]

    def get_drill(self, drill_id: str) -> dict[str, Any]:
        self._hit("get_drill", drill_id)
        if drill_id == "nope":
            raise UnknownDrillError(drill_id)
        rows = [[str(i)] for i in range(300)]
        return {
            "meta": {**META, "id": drill_id},
            "task_md": "List every customer.",
            "schema_sql": "CREATE TABLE c (id INT);",
            "tables": {"c": {"columns": ["id"], "rows": rows}},
            "expected_preview": [["1"]],
        }

    def run(self, drill_id: str, sql_text: str) -> dict[str, Any]:
        self._hit("run", (drill_id, sql_text))
        return self.run_result

    def check_prediction(self, drill_id: str, grid: list[list[str]]) -> dict[str, Any]:
        self._hit("check_prediction", (drill_id, grid))
        return {"match": False, "cell_diff": [(0, 0, "1", "2")], "actual_rows": [["2"]]}

    def save_generated(self, spec: dict[str, str]) -> str:
        self._hit("save_generated", spec)
        if self.save_errors:
            raise self.save_errors.pop(0)
        self.saved.append(spec)
        return "g2"


def install_fake_sd(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    """Make ``sql.load_sd`` return a fresh fake."""
    fake = FakeSd()
    monkeypatch.setattr(sql, "load_sd", lambda: fake)
    return fake


def install_fake_fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    """Make the heartbeat's ``focus_hook.load_fp`` return a fresh fake."""
    fake = FakeFp()
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)
    return fake


def validate(kind: str, body: dict[str, Any]) -> protocol.Request:
    req = {"kind": kind, "dev": DEV, "created": int(NOW * 1000), "body": body}
    return protocol.validate(RID, req)


def call(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run the chat handler of ``kind`` on a validated body."""
    ctx = SimpleNamespace(
        now=lambda: NOW,
        request=SimpleNamespace(created_ms=int(NOW * 1000)),
        body=validate(kind, body).body,
    )
    return asyncio.run(CHAT_HANDLERS[kind](cast("RequestContext", ctx)))
