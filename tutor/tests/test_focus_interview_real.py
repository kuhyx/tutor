# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The relay against the real ``focus_project`` 0.9 registry (call-shape contract).

Skipped until the installed focus_project has the interview API; run it before
that with ``PYTHONPATH=~/src/utils/focus_project``.
"""

from __future__ import annotations

import asyncio
from datetime import date
import importlib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from tutor import credit, focus_hook
from tutor.relay import protocol
from tutor.relay.chat import CHAT_HANDLERS
from tutor.relay.errors import RequestError
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._focus_support import CREATED, DEV, NOW, RID, Subjects
from tutor.tests._interview_support import INTERVIEW

if TYPE_CHECKING:
    from pathlib import Path

fp = focus_hook.load_fp()
pytestmark = pytest.mark.skipif(
    fp is None or not hasattr(fp, "record_evidence"),
    reason="focus_project >= 0.9.0 is not installed",
)
TODAY = date.fromisoformat(credit.local_day(NOW)[0])
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64


def call(kind: str, body: dict[str, Any], rtdb: FakeRtdb | None = None) -> Any:
    req = {"kind": kind, "dev": DEV, "created": CREATED, "body": body}
    ctx = SimpleNamespace(
        now=lambda: NOW,
        request=SimpleNamespace(created_ms=CREATED),
        body=protocol.validate(RID, req).body,
        rtdb=(rtdb or FakeRtdb()).rtdb(),
        engine=SimpleNamespace(ctx=SimpleNamespace(subjects=Subjects())),
    )
    handler = CHAT_HANDLERS[kind]
    return asyncio.run(handler(cast("Any", ctx)))


def test_create_status_evidence_trip_and_ratchet_on_the_real_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from focus_project.sources import activity

    monkeypatch.setattr(activity, "sessions", lambda _id: [(0.0, 5400.0)])
    made = call("focus_create", INTERVIEW | {"no_trip": True, "name": "Codility"})
    pid = made["id"]
    active = call("focus_status", {})["active"]
    assert (active["kind"], active["id"]) == ("interview", pid)
    assert {m["id"] for m in active["milestones"]} >= {"rules", "mock", "slot"}
    assert active["daily_minutes"] == 30  # Friday: the weekday target

    tap = {"id": pid, "milestone": "slot", "kind": "slot", "value": "2027-01-19T09:00"}
    call("focus_evidence", tap)
    call("focus_evidence", {**tap, "kind": "slot_confirm", "value": True})
    done = call(
        "focus_evidence", {"id": pid, "milestone": "mock", "kind": "score", "value": 80}
    )
    states = {m["id"]: m["state"] for m in done["milestones"]}
    assert states["slot"] == "done"
    assert states["mock"] == "done"

    trip = {"id": pid, "start": "2027-01-16", "end": "2027-01-17"}
    got = call("focus_trip", trip)
    assert got["trips"] == [{"start": "2027-01-16", "end": "2027-01-17"}]
    assert got["weekend_answers"] == {"2027-01-16": True}
    with pytest.raises(RequestError) as caught:
        call("focus_weekend", {"id": pid, "saturday": "2027-01-16", "trip": False})
    assert caught.value.code == "focus_refused"
    assert "stricter" in caught.value.message or "stays True" in caught.value.message
    with pytest.raises(RequestError) as shrunk:
        call("focus_trip", {**trip, "end": "2027-01-16"})
    assert shrunk.value.code == "focus_refused"


def test_a_refused_tap_on_the_rules_milestone_is_loud() -> None:
    pid = call("focus_create", INTERVIEW | {"no_trip": True})["id"]
    with pytest.raises(RequestError) as caught:
        call("focus_evidence", {"id": pid, "milestone": "rules", "kind": "tap"})
    assert caught.value.code == "focus_refused"
    assert "takes evidence kinds" in caught.value.message
    assert TODAY.year == 2027


def test_the_phone_report_is_accepted_and_latches_a_check(tmp_path: Path) -> None:
    from tutor.relay.phone_check import PhoneCheck
    from tutor.tests._cur import make_ctx

    trips = [{"start": "2027-01-16", "end": "2027-01-17"}]
    pid = call("focus_create", INTERVIEW | {"trips": trips})["id"]
    fake = FakeRtdb()
    fake.set(
        "tutor/v1/presence/clients/phone", {"platform": "android", "seen": CREATED}
    )
    wiring = SimpleNamespace(
        rtdb=fake.rtdb(),
        engine=SimpleNamespace(ctx=make_ctx(tmp_path / "cur")[0]),
        now=lambda: NOW,
    )
    asyncio.run(PhoneCheck(cast("Any", wiring)).tick())
    rows = importlib.import_module("focus_project.evidence").read(pid)
    report = [r for r in rows if r.kind == "phone_check"]
    assert report[0].value == {"plan": False, "due": 0, "seen_ms": CREATED}
    assert any(r.kind == "check" and r.value is False for r in rows)
