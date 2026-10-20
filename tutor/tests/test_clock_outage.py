# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A backend outage never counts against the learner (kuhy, 2026-10-11).

Only a reply in flight is excused (2026-10-20): idle time across a restart
earns nothing, exactly like idle time without one.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tutor import resume
from tutor.clock import (
    OUTAGE_CAP,
    REPLY_TIMEOUT,
    SEND_GRACE,
    STALLED,
    EngagementClock,
    reply_time,
)

if TYPE_CHECKING:
    from pathlib import Path

T0 = 1_000_000.0
ANSWER = "the rack holds the power supply, the CPU and the I/O cards"


def test_a_9_minute_reply_earns_and_an_11_minute_one_does_not() -> None:
    clock = EngagementClock(T0)
    clock.tutor_message(T0)
    clock.user_reply(T0 + 9 * 60, ANSWER, low_effort=False)
    assert clock.active_seconds == 9 * 60
    late = EngagementClock(T0)
    late.tutor_message(T0)
    late.user_reply(T0 + 11 * 60, ANSWER, low_effort=False)
    assert late.active_seconds == 0
    assert late.snapshot()["paused_reason"] == STALLED


def test_a_restart_inside_the_window_starts_it_over() -> None:
    clock = EngagementClock(T0)
    clock.tutor_message(T0)
    clock.server_restarted(T0 + 500, pending_at=T0 + 450)
    assert clock.snapshot(T0 + REPLY_TIMEOUT + 60)["paused"] is False
    assert clock.snapshot(T0 + 500 + REPLY_TIMEOUT + 1)["paused_reason"] == STALLED
    clock.user_reply(T0 + 1000, ANSWER, low_effort=False)
    assert clock.active_seconds == 1000  # the whole gap, outage included


def test_a_restart_excuse_is_capped() -> None:
    clock = EngagementClock(T0)
    clock.tutor_message(T0)
    clock.server_restarted(T0 + OUTAGE_CAP - 60, pending_at=T0 + 60)
    clock.user_reply(T0 + OUTAGE_CAP + 1, ANSWER, low_effort=False)
    assert clock.active_seconds == 0


def test_a_restart_with_no_open_window_excuses_nothing() -> None:
    clock = EngagementClock(T0)
    clock.server_restarted(T0, pending_at=T0)
    clock.excuse_restart(T0)  # the replayed pre-2026-10-20 rule: nothing either
    clock.tutor_message(T0 + 10)
    clock.user_reply(T0 + 10 + REPLY_TIMEOUT + 1, ANSWER, low_effort=False)
    assert clock.active_seconds == 0


def test_the_next_tutor_message_drops_an_old_restart() -> None:
    clock = EngagementClock(T0)
    clock.tutor_message(T0)
    clock.server_restarted(T0 + 100, pending_at=T0 + 90)
    clock.user_reply(T0 + 200, ANSWER, low_effort=False)
    clock.tutor_message(T0 + 210)
    assert clock.snapshot(T0 + 210 + REPLY_TIMEOUT + 1)["paused_reason"] == STALLED


def test_a_restart_with_no_reply_in_flight_excuses_nothing() -> None:
    clock = EngagementClock(T0)
    clock.tutor_message(T0)
    clock.server_restarted(T0 + 500, pending_at=None)  # the learner was idle
    assert clock.snapshot(T0 + REPLY_TIMEOUT + 1)["paused_reason"] == STALLED
    clock.user_reply(T0 + 1000, ANSWER, low_effort=False)
    assert clock.active_seconds == 0


def test_a_late_reply_in_flight_is_not_excused() -> None:
    """A reply that was already past the window had nothing to lose."""
    clock = EngagementClock(T0)
    clock.tutor_message(T0)
    clock.server_restarted(T0 + 700, pending_at=T0 + REPLY_TIMEOUT + 1)
    clock.user_reply(T0 + 800, ANSWER, low_effort=False)
    assert clock.active_seconds == 0


def _replayed_seconds(tmp_path: Path, restart: dict[str, Any]) -> float:
    events = [
        {"type": "start", "card": "c", "t": T0},
        {"type": "tutor", "t": T0, "turn": {"message": "Why?"}},
        {"type": "resume", "t": T0 + 500, **restart},
        {"type": "learner", "text": ANSWER, "t": T0 + 1000, "msg_id": "m1"},
        {"type": "tutor", "t": T0 + 1000, "turn": {"message": "Yes."}},
    ]
    path = tmp_path / "s.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    state = resume.replay(path)
    assert state is not None
    return state.conversation.clock.active_seconds


def test_replay_excuses_a_restart_only_as_logged(tmp_path: Path) -> None:
    assert _replayed_seconds(tmp_path, {"pending_at": None}) == 0
    assert _replayed_seconds(tmp_path, {"pending_at": T0 + 450}) == 1000
    # Logged before 2026-10-20 (no ``pending_at``): every restart was excused,
    # and the ledger already pays those minutes, so the replay keeps them.
    assert _replayed_seconds(tmp_path, {}) == 1000


def test_reply_time_trusts_the_first_send_press_only_within_grace() -> None:
    assert reply_time(T0, T0 - 100) == T0 - 100
    assert reply_time(T0, T0 - SEND_GRACE) == T0 - SEND_GRACE
    assert reply_time(T0, T0 - SEND_GRACE - 1) == T0
    assert reply_time(T0, T0 + 5) == T0  # a page clock ahead of the server
    assert reply_time(T0, None) == T0
