# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Engine-level outage excuses: restarts and retried sends (kuhy, 2026-10-11)."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.clock import GENERATION_CAP, REPLY_TIMEOUT, SEND_GRACE
from tutor.delivery import Delivery
from tutor.engine import Engine
from tutor.ledger_io import default_paths
from tutor.store import Store
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from pathlib import Path

CARD = "io-24vdc-relay-coil"
ANSWER = "the coil becomes a magnet and pulls the contact closed"


def make(tmp_path: Path, fake: FakeSession, clock: ManualClock, **kw: Any) -> Engine:
    kw.setdefault("credit_fn", FakeCredit())  # ``None``: the real signed ledger
    return Engine(
        store=Store(tmp_path / "data"),
        now=clock,
        session_factory=lambda _prompt: fake,
        **kw,
    )


def test_a_retried_send_is_timed_from_the_first_press(tmp_path: Path) -> None:
    clock = ManualClock()
    engine = make(tmp_path, FakeSession(turn(), turn()), clock)
    asyncio.run(engine.start(CARD))
    pressed = clock.t + REPLY_TIMEOUT - 30
    clock.advance(REPLY_TIMEOUT - 30 + SEND_GRACE)  # arrives 5 min after the press
    state = asyncio.run(engine.reply(ANSWER, msg_id="m1", via=Delivery(pressed)))
    # The press-to-tutor wait then counts as generation, capped as ever.
    assert state["clock"]["active_seconds"] == REPLY_TIMEOUT - 30 + GENERATION_CAP


def test_a_restart_with_a_reply_in_flight_excuses_the_window(tmp_path: Path) -> None:
    """The 2026-10-11 session: a deploy mid-reply, the resend past the window."""
    clock = ManualClock()
    first = make(tmp_path, FakeSession(turn(), RuntimeError("deploy")), clock)
    asyncio.run(first.start(CARD))
    clock.advance(REPLY_TIMEOUT - 60)
    with pytest.raises(RuntimeError):  # logged, then the server went down
        asyncio.run(first.reply(ANSWER, msg_id="m1"))
    clock.advance(60)
    second = make(tmp_path, FakeSession(turn()), clock)
    assert second.resume_latest() is True
    clock.advance(300)  # past the 10 min since the tutor spoke
    assert second.state()["clock"]["paused"] is False
    state = asyncio.run(second.reply(ANSWER, msg_id="m1"))
    assert state["clock"]["active_seconds"] == REPLY_TIMEOUT + 300
    third = make(tmp_path, FakeSession(), clock)  # the replay agrees
    assert third.resume_latest() is True
    assert third.state()["clock"]["active_seconds"] == REPLY_TIMEOUT + 300


def test_a_restart_while_idle_at_card_end_excuses_nothing(tmp_path: Path) -> None:
    """2026-10-20 E2E: a deploy while idle at card end minted 47 min on a follow-up."""
    clock = ManualClock()
    fake = FakeSession(turn(), turn("Done.", card_done=True))
    first = make(tmp_path, fake, clock, credit_fn=None)
    asyncio.run(first.start(CARD))
    clock.advance(120)
    asyncio.run(first.reply(ANSWER, msg_id="m1"))
    clock.advance(47 * 60)  # idle at card end, then a deploy
    second = make(tmp_path, FakeSession(turn("Sure.")), clock, credit_fn=None)
    assert second.resume_latest() is True
    clock.advance(120)
    state = asyncio.run(second.reply("why 24 V and not 230 V?", msg_id="f1"))
    assert state["clock"]["active_seconds"] == 120  # the idle gap earned nothing
    ledger = default_paths().ledger
    rows = json.loads(ledger.read_text())["entries"]
    assert [r["detail"]["minutes"] for r in rows] == [2]
    third = make(tmp_path, FakeSession(), clock, credit_fn=None)
    assert third.resume_latest() is True  # a replay rebuilds the same credit
    assert third.state()["clock"]["active_seconds"] == 120
    assert json.loads(ledger.read_text())["entries"] == rows


def test_resume_keeps_a_larger_total_backfill_paid(tmp_path: Path) -> None:
    """2026-10-11: backfill paid 6 more minutes, resume then showed only 3."""
    clock = ManualClock()
    engine = make(tmp_path, FakeSession(turn()), clock)
    asyncio.run(engine.start(CARD))
    engine._set_today(9)  # what backfill_today leaves behind
    assert engine.resume_latest() is True
    assert engine.minutes_today == 9
