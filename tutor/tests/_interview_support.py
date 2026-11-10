# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared wiring for the interview relay tests: a fake fp 0.9 and a call helper."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from tutor import focus_hook
from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.tests._fake_fp_interview import FakeInterviewFp, FakeMilestone
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._focus_support import CREATE, CREATED, DEV, NOW, RID, Subjects

if TYPE_CHECKING:
    import pytest

    from tutor.relay.context import RequestContext
    from tutor.tests._fake_fp import FakeProject

# 2027-01-15 is a Friday; the test is on Wednesday the 20th.
TEST_DAY = date(2027, 1, 20)


def naive(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """A naive local datetime, the shape focus_project takes."""
    return datetime(year, month, day, hour, minute, tzinfo=UTC).replace(tzinfo=None)


NOW_LOCAL = datetime.fromtimestamp(NOW, tz=UTC).astimezone().replace(tzinfo=None)
INTERVIEW: dict[str, Any] = {
    **CREATE,
    "end": "2027-01-20",
    "daily_minutes": 30,
    "unlock_minutes": 30,
    "kind": "interview",
    "test_at": "2027-01-20T10:00",
    "invite_url": "https://app.codility.com/c/run/abc",
}


def install(monkeypatch: pytest.MonkeyPatch) -> FakeInterviewFp:
    """Make ``focus_hook.load_fp`` return a fresh interview fake."""
    fake = FakeInterviewFp()
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)
    return fake


def ms(id_: str, state: str = "pending") -> FakeMilestone:
    return FakeMilestone(id_, naive(2027, 1, 16, 23, 59), state)


def call(
    kind: str, body: dict[str, Any], rtdb: FakeRtdb | None = None
) -> dict[str, Any]:
    """Run the chat handler of ``kind`` on a validated body."""
    req = {"kind": kind, "dev": DEV, "created": CREATED, "body": body}
    ctx = SimpleNamespace(
        now=lambda: NOW,
        request=SimpleNamespace(created_ms=CREATED),
        body=protocol.validate(RID, req).body,
        rtdb=(rtdb or FakeRtdb()).rtdb(),
        engine=SimpleNamespace(ctx=SimpleNamespace(subjects=Subjects())),
    )
    return asyncio.run(CHAT_HANDLERS[kind](cast("RequestContext", ctx)))


def interview_project(fake: FakeInterviewFp, **kw: Any) -> FakeProject:
    """An interview project active today (2027-01-15 .. 2027-01-20)."""
    return fake.create_project(
        "codility",
        name="Codility",
        start=date(2027, 1, 15),
        end=TEST_DAY,
        replaces=["tutor"],
        daily_minutes=30,
        unlock_minutes=30,
        kind="interview",
        test_at=naive(2027, 1, 20, 10, 0),
        invite_url="https://app.codility.com/c/run/abc",
        **kw,
    )
