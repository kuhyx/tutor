# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the problem-coach tests: fake coach, runner and model."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from tutor import focus_hook
from tutor.relay import lc_backend, lc_cards, lc_state, protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.tests._fake_fp import FakeFp

if TYPE_CHECKING:
    import pytest

    from tutor.relay.context import RequestContext

RID = "01J00000000000000000000000"
DEV = "00000000-0000-4000-8000-000000000000"
NOW = 1_800_000_000.0
ALGO = lc_backend.Problem(
    "two-sum",
    "Two Sum",
    "easy",
    "Given nums and target, return the indices.\nExample: nums = [2,7]",
    {"python3": "def twoSum(nums, target):\n    pass", "javascript": "x"},
    "algo",
)
SQL = lc_backend.Problem(
    "reformat",
    "Reformat Table",
    "medium",
    "Table: Department\n| id | revenue |\nOutput:\n| id | Jan_Revenue |\n| 1 | 8 |",
    {"mysql": "SELECT 1"},
    "sql",
)
TOOLBOX = (
    [
        {"name": "XOR", "aliases": ["^"], "properties": ["self-inverse", "order-free"]},
        {"name": "hash map", "aliases": [], "properties": ["lookup"]},
    ],
    {"self-inverse": "a^a=0", "order-free": "x", "lookup": "y", "ordered": "z"},
)


def reply(text: str, rung: str = "", belief: str = "") -> dict[str, Any]:
    return {"reply_md": text, "rung": rung, "belief": belief}


@dataclass
class Fakes:
    """Scripted model answers and recorded backend calls."""

    problem: lc_backend.Problem = ALGO
    fetch_error: Exception | None = None
    replies: list[Any] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    verdicts: list[lc_backend.Verdict] = field(default_factory=list)
    logs: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    appended: list[tuple[str, list[str], list[str]]] = field(default_factory=list)
    append_error: Exception | None = None
    anki: list[list[dict[str, str]]] = field(default_factory=list)
    anki_error: Exception | None = None
    anki_line: str | None = None
    run_report: dict[str, Any] = field(
        default_factory=lambda: {"ok": True, "examples": [{"n": 1, "ok": True}]}
    )
    run_error: Exception | None = None
    runs: list[tuple[str, str, str]] = field(default_factory=list)
    fp: FakeFp = field(default_factory=FakeFp)
    box: list[dict[str, Any]] = field(
        default_factory=lambda: [dict(e) for e in TOOLBOX[0]]
    )

    def model(self, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        del schema
        self.prompts.append(prompt)
        answer = self.replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return dict(answer)

    def fetch(self, problem: str) -> lc_backend.Problem:
        del problem
        if self.fetch_error is not None:
            raise self.fetch_error
        return self.problem

    def check_req(self, statement: str, text: str, ask: Any) -> lc_backend.Verdict:
        del statement, text, ask
        return self.verdicts.pop(0)

    def leaked(self, text: str, said: list[str]) -> list[str]:
        heard = " ".join(said).lower()
        return [
            e["name"]
            for e in self.box
            if e["name"].lower() in text.lower() and e["name"].lower() not in heard
        ]

    def append_entry(self, name: str, aliases: list[str], props: list[str]) -> None:
        if self.append_error is not None:
            raise self.append_error
        self.appended.append((name, aliases, props))
        self.box.append({"name": name, "aliases": aliases, "properties": props})

    def deliver_anki(self, cards: list[dict[str, str]]) -> str:
        if self.anki_error is not None:
            raise self.anki_error
        self.anki.append(cards)
        return self.anki_line or f"{len(cards)} cards -> Anki"

    def log(self, slug: str, event: str, **fields: object) -> None:
        self.logs.append((slug, event, dict(fields)))

    def run(self, lang: str, code: str, statement: str, starter: str) -> dict[str, Any]:
        self.runs.append((lang, code, starter))
        if self.run_error is not None:
            raise self.run_error
        return dict(self.run_report)

    def events(self) -> list[str]:
        return [e for _, e, _ in self.logs]


def install(monkeypatch: pytest.MonkeyPatch, fakes: Fakes | None = None) -> Fakes:
    """Install a fresh fake coach, runner and model; a fresh FakeFp heartbeat."""
    fakes = fakes or Fakes()
    coach = lc_backend.Coach(
        fetch=fakes.fetch,
        system_prompt=lambda statement: "SYS " + statement[:5],
        check_req=fakes.check_req,
        leaked=fakes.leaked,
        toolbox=lambda: (list(fakes.box), TOOLBOX[1]),
        append_entry=fakes.append_entry,
        deliver_anki=fakes.deliver_anki,
        log=fakes.log,
        clusters=lambda: [{"name": "bits", "problems": ["two-sum"]}],
        due=lambda: [{"slug": "two-sum", "title": "Two Sum", "due_ms": 1}],
    )
    lc_backend.install(coach, fakes.run)
    for module in (
        "tutor.relay.lc_reply",
        "tutor.relay.lc_exit",
        "tutor.relay.lc_turn",
    ):
        monkeypatch.setattr(f"{module}.ask_model", fakes.model)
    monkeypatch.setattr(lc_cards, "ask_model", fakes.model)
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fakes.fp)
    return fakes


def validate(kind: str, body: dict[str, Any]) -> protocol.Request:
    req = {"kind": kind, "dev": DEV, "created": int(NOW * 1000), "body": body}
    return protocol.validate(RID, req)


def call(
    kind: str,
    body: dict[str, Any],
    engine_ctx: Any = None,
    sent_at_ms: int | None = None,
) -> dict[str, Any]:
    """Run the chat handler of ``kind`` on a validated body."""
    ctx = SimpleNamespace(
        now=lambda: NOW,
        request=SimpleNamespace(created_ms=int(NOW * 1000), sent_at_ms=sent_at_ms),
        body=validate(kind, body).body,
        engine=SimpleNamespace(ctx=engine_ctx),
    )
    return asyncio.run(CHAT_HANDLERS[kind](cast("RequestContext", ctx)))


def stored(lc_id: str) -> lc_state.State:
    return lc_state.load(lc_id)


def open_session(
    fakes: Fakes, *, lang: str | None = None, opener: str = "Restated. Which part?"
) -> str:
    """Open a session on ``fakes.problem`` and return its ``lc_id``."""
    fakes.replies.append(reply(opener))
    body: dict[str, Any] = {"problem": "https://leetcode.com/problems/x/"}
    if lang:
        body["lang"] = lang
    return str(call("lc_open", body)["lc_id"])


def turn(lc_id: str, text: str, intent: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"lc_id": lc_id, "text": text}
    if intent:
        body["intent"] = intent
    return call("lc_turn", body)


def gated_open(fakes: Fakes, lc_id: str) -> None:
    """Open the gate through a passing ``req:``/``shape:`` message."""
    prefix = "shape" if fakes.problem.kind == "sql" else "req"
    fakes.verdicts.append(("pass", ()))
    turn(lc_id, f"{prefix}: id Jan_Revenue")
