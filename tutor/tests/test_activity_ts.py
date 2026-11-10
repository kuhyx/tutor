# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Beats carry the answer's own time (focus_project 0.10.0 backing)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tutor import clock, credit, focus_hook, unit_credit
from tutor.clock import BlockReady
from tutor.relay import lc_reply, sql
from tutor.tests import _lc_support as lcs
from tutor.tests import _sql_support as sqs
from tutor.tests._fake_fp import FakeFp, FakeProject

if TYPE_CHECKING:
    from tutor.tests._fake_fp import FakeFp as Fp

NOON = 1_800_000_000.0
H = 3600.0
WEEK = 48 * H


@pytest.mark.parametrize(
    ("sent_at", "want"),
    [
        (NOON - 120, NOON - 120),  # past, in window
        (None, NOON),  # absent
        (NOON + 5, NOON),  # future: never ahead of the clock
        (NOON - WEEK, NOON - WEEK),  # exactly 48 h old
        (NOON - WEEK - 1, NOON),  # over 48 h
        (NOON, NOON),
    ],
)
def test_activity_time_clamps(sent_at: float | None, want: float) -> None:
    assert clock.activity_time(NOON, sent_at) == want


def test_reply_time_is_unchanged_for_credit() -> None:
    assert clock.reply_time(NOON, NOON - 600) == NOON  # outside the send grace


def _project() -> FakeProject:
    day = date.fromisoformat(credit.local_day(NOON)[0])
    return FakeProject("exam", "Exam", day, day, ("tutor",), 60, 10, ("sql",))


def test_focus_hook_heartbeat_passes_ts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeFp([_project()])
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)
    focus_hook.heartbeat("sql", NOON, NOON - 90)
    focus_hook.heartbeat("sql", NOON, None)
    assert [a["ts"] for a in fake.activity] == [NOON - 90, None]


def test_credit_units_beats_at_the_unit_time(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeFp([_project()])
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)
    unit = BlockReady(1, 60.0, NOON - 700, 2, 3)  # an offline answer, synced late
    unit_credit.credit_units([unit], "ts1", now=NOON, subject="sql")
    assert fake.activity[0]["ts"] == NOON - 700


def test_credit_units_future_unit_time_falls_back_to_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeFp([_project()])
    monkeypatch.setattr(focus_hook, "load_fp", lambda: fake)
    unit = BlockReady(1, 60.0, NOON + 900, 2, 3)
    unit_credit.credit_units([unit], "ts2", now=NOON, subject="sql")
    assert fake.activity[0]["ts"] == NOON


@pytest.mark.parametrize(
    ("sent_ms", "want"),
    [
        (int((sqs.NOW - 300) * 1000), sqs.NOW - 300),
        (None, sqs.NOW),
        (int((sqs.NOW + 60) * 1000), sqs.NOW),
        (int((sqs.NOW - WEEK - 5) * 1000), sqs.NOW),
    ],
)
def test_sql_run_beats_at_the_clamped_send_time(
    monkeypatch: pytest.MonkeyPatch, sent_ms: int | None, want: float
) -> None:
    sqs.install_fake_sd(monkeypatch)
    fp: Fp = sqs.install_fake_fp(monkeypatch)
    sqs.call("sql_run", {"id": "q1", "sql": "SELECT 1"}, sent_at_ms=sent_ms)
    assert fp.activity[0]["ts"] == want


def test_sql_heartbeat_passes_ts_through(monkeypatch: pytest.MonkeyPatch) -> None:
    fp = sqs.install_fake_fp(monkeypatch)
    sql.heartbeat(NOON - 5)
    assert fp.activity == [
        {"source": "sql_drills", "kind": "heartbeat", "ts": NOON - 5}
    ]


def test_lc_heartbeat_passes_ts_through(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = lcs.install(monkeypatch)
    lc_reply.heartbeat(NOON - 5)
    assert fakes.fp.activity == [
        {"source": "tutor", "kind": "heartbeat", "ts": NOON - 5}
    ]


def test_lc_turn_beats_at_the_send_time(monkeypatch: pytest.MonkeyPatch) -> None:
    fakes = lcs.install(monkeypatch)
    lc_id = lcs.open_session(fakes)
    fakes.fp.activity.clear()
    fakes.replies.append(lcs.reply("Say more."))
    lcs.call(
        "lc_turn",
        {"lc_id": lc_id, "text": "I think it is about pairs of numbers"},
        sent_at_ms=int((lcs.NOW - 200) * 1000),
    )
    assert [a["ts"] for a in fakes.fp.activity] == [lcs.NOW - 200]
