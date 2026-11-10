# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Shared rig for the phone-check tests: a PhoneCheck on a fake database."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from tutor import credit
from tutor.relay.phone_check import PhoneCheck
from tutor.store import data_dir
from tutor.tests._cur import card, make_ctx, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._interview_support import NOW_LOCAL, naive

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.tests._fake_fp_interview import FakeInterviewFp

NOW = 1_800_000_000.0  # 2027-01-15 09:00 Warsaw
NOW_MS = int(NOW * 1000)
DAY = credit.local_day(NOW)[0]
STAMP = NOW_LOCAL
PHONE = "107cb1bf-a093-416a-b356-a995e13f73fe"
WEB = "00000000-0000-4000-8000-000000000001"


class Rig:
    """A PhoneCheck over a fake database, a real curriculum and a mutable clock."""

    def __init__(self, tmp_path: Path, fp: FakeInterviewFp) -> None:
        self.fake = FakeRtdb()
        self.now = NOW
        self.cur = make_ctx(tmp_path / "cur")[0]
        subject(self.cur, "hosting", found={f"c{i}": card("a", i) for i in range(3)})
        wiring = SimpleNamespace(
            rtdb=self.fake.rtdb(),
            engine=SimpleNamespace(ctx=self.cur),
            now=lambda: self.now,
        )
        self.check = PhoneCheck(cast("Any", wiring))
        self.fp = fp

    def presence(self, seen: int | None, platform: str = "android") -> None:
        node: dict[str, Any] = {"platform": platform, "app": "1"}
        if seen is not None:
            node["seen"] = seen
        self.fake.set(f"tutor/v1/presence/clients/{PHONE}", node)

    def reports(self) -> list[dict[str, Any]]:
        return [a for n, a in self.fp.calls if n == "record_evidence"]


def write_plan(*, steps: bool = True) -> None:
    path = data_dir() / "plan" / f"{DAY}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"id": "s", "title": "s", "what": "w", "kind": "note", "target": ""}]
    path.write_text(json.dumps({"steps": rows if steps else []}), encoding="utf-8")


def interview_fp(fake: FakeInterviewFp) -> FakeInterviewFp:
    """Add the interview project the rig reports on (subjects: one real, two not)."""
    fake.create_project(
        "codility",
        name="Codility",
        start=naive(2027, 1, 15).date(),
        end=naive(2027, 1, 20).date(),
        replaces=["tutor"],
        daily_minutes=30,
        unlock_minutes=30,
        subjects=["hosting", "nope", "../x"],
        kind="interview",
        test_at=naive(2027, 1, 20, 10, 0),
    )
    return fake
