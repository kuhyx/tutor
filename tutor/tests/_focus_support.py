# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the focus relay tests: ctx, calls, a fake ``focus_project``."""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from tutor import credit, focus_hook
from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.tests._fake_fp import FakeFp, FakeProject

if TYPE_CHECKING:
    import pytest

    from tutor.relay.context import RequestContext

RID = "01J00000000000000000000000"
DEV = "00000000-0000-4000-8000-000000000000"
NOW = 1_800_000_000.0  # 2027-01-15 08:00 UTC
CREATED = int(NOW * 1000)
TODAY = date.fromisoformat(credit.local_day(NOW)[0])
HOUR_MS = 3_600_000
CREATE: dict[str, Any] = {
    "name": "Exam prep",
    "start": "2027-01-15",
    "end": "2027-01-20",
    "replaces": ["leetcode", "reading"],
    "daily_minutes": 120,
    "unlock_minutes": 30,
    "subjects": ["sql"],
    "site_patterns": ["leetcode.com"],
    "work_url": "https://leetcode.com/problemset/",
}


def day(offset: int) -> date:
    return date.fromordinal(TODAY.toordinal() + offset)


def project(pid: str, start: int, end: int, created: int = 1, **kw: Any) -> FakeProject:
    """A tutor-replacing project from ``start`` to ``end`` days off today."""
    return FakeProject(
        pid,
        pid.title(),
        day(start),
        day(end),
        ("tutor",),
        60,
        10,
        created_ms=created,
        **kw,
    )


class Subjects:
    """The engine's subject store, two subjects."""

    def subjects(self) -> list[str]:
        return ["sql", "go"]

    def meta(self, subject: str) -> SimpleNamespace:
        return SimpleNamespace(title=subject.upper())


def install_fake_fp(monkeypatch: pytest.MonkeyPatch) -> FakeFp:
    """Make ``focus_hook.load_fp`` return a fresh fake."""
    fake = FakeFp()
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)
    return fake


def validate(kind: str, body: dict[str, Any]) -> protocol.Request:
    req = {"kind": kind, "dev": DEV, "created": CREATED, "body": body}
    return protocol.validate(RID, req)


def call(kind: str, body: dict[str, Any], created: int = CREATED) -> dict[str, Any]:
    """Run the chat handler of ``kind`` on a validated body."""
    ctx = SimpleNamespace(
        now=lambda: NOW,
        request=SimpleNamespace(created_ms=created),
        body=validate(kind, body).body,
        engine=SimpleNamespace(ctx=SimpleNamespace(subjects=Subjects())),
    )
    return asyncio.run(CHAT_HANDLERS[kind](cast("RequestContext", ctx)))
