# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the mock-test relay tests: fake engine, fake model, calls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import shutil
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from tutor import focus_hook
from tutor.relay import mock_mcq, mock_sql, protocol, sql
from tutor.relay.chat import CHAT_HANDLERS
from tutor.tests._fake_fp import FakeFp

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

RID = "01J00000000000000000000000"
DEV = "00000000-0000-4000-8000-000000000000"
NOW = 1_800_000_000.0
needs_bwrap = pytest.mark.skipif(shutil.which("bwrap") is None, reason="no bwrap")


@dataclass(frozen=True)
class Meta:
    """A ``DrillMeta`` stand-in."""

    id: str
    title: str
    topic: str
    kind: str
    source: str


DRILLS = [
    Meta("08_anti_join", "Anti join", "joins-null", "write", "builtin"),
    Meta("09_group_having", "Having", "group-having", "write", "builtin"),
    Meta("01_pivot_sum", "Pivot", "pivot", "write", "builtin"),
    Meta("03_month_bucket", "Months", "dates", "write", "builtin"),
    Meta("06_number_traps", "Numbers", "number-format", "write", "builtin"),
    Meta("t01_null", "Predict", "basics", "predict", "builtin"),
]


@dataclass
class FakeSd:
    """Records calls; ``good`` is the SQL text the fake engine accepts."""

    good: str = "SELECT 1"
    calls: list[tuple[str, Any]] = field(default_factory=list)
    saved: list[dict[str, str]] = field(default_factory=list)

    def ensure_running(self) -> None:
        self.calls.append(("ensure", None))

    def list_drills(self) -> list[Meta]:
        return DRILLS

    def get_drill(self, drill_id: str) -> dict[str, Any]:
        topic = next(m.topic for m in [*DRILLS, Meta("g1", "G", "dates", "write", "g")]
                     if m.id == drill_id)  # fmt: skip
        return {
            "meta": {"id": drill_id, "title": "Secret technique", "topic": topic},
            "task_md": "List ids.",
            "schema_sql": "CREATE TABLE t (id INT);",
            "tables": {"t": {"columns": ["id"], "rows": [["1"], ["2"]]}},
            "expected_preview": [["1"], ["2"], ["3"], ["4"], ["5"], ["6"], ["7"]],
        }

    def run(self, drill_id: str, text: str) -> dict[str, Any]:
        self.calls.append(("run", (drill_id, text)))
        ok = text.strip() != "BROKEN"
        return {
            "ok": ok,
            "error": None if ok else "syntax error",
            "match": text == self.good,
            "columns": ["id"],
            "rows": [["1"]],
            "expected_rows": [["1"], ["2"]],
            "cell_diff": [(0, 0, "1", "2")],
            "extra_rows": [],
            "missing_rows": [],
        }

    def save_generated(self, spec: dict[str, str]) -> str:
        self.saved.append(spec)
        return "g1"


def install(monkeypatch: pytest.MonkeyPatch) -> FakeSd:
    """A fake engine and focus API for every mock handler."""
    fake = FakeSd()
    monkeypatch.setattr(sql, "load_sd", lambda: fake)
    monkeypatch.setattr(focus_hook, "load_fp", FakeFp)
    return fake


QUESTION = {
    "topic": "slicing",
    "code": "print('abc'[::-1])",
    "wrong_outputs": ["abc", "cba ", "bca"],
}


def model(
    monkeypatch: pytest.MonkeyPatch, questions: list[dict[str, Any]], spec: bool = True
) -> None:
    """Fake ``ask_model``: MCQ batches get ``questions``, drill specs a spec."""

    def fake_mcq(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del system, prompt, schema
        return {"questions": questions}

    def fake_spec(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del system, prompt, schema
        if not spec:
            msg = "model down"
            raise RuntimeError(msg)
        return dict.fromkeys(
            ("title", "topic", "task_md", "schema_sql", "reference_sql"), "x"
        )

    monkeypatch.setattr(mock_mcq, "ask_model", fake_mcq)
    monkeypatch.setattr(mock_sql, "ask_model", fake_spec)


def call(body: dict[str, Any]) -> dict[str, Any]:
    """Validate ``body`` as a ``mock`` request and run its handler."""
    req = {"kind": "mock", "dev": DEV, "created": int(NOW * 1000), "body": body}
    ctx = SimpleNamespace(
        now=lambda: NOW, body=protocol.validate(RID, req).body, request=None
    )
    return asyncio.run(CHAT_HANDLERS["mock"](cast("RequestContext", ctx)))
