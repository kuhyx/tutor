# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``stats.today.active_minutes``: the day's engaged time across sessions.

A new card is a new session, so the Session header shows the day's totals
(kuhy, 2026-10-12: after Next card it dropped to "Active 0 min").
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from tutor.curriculum.stats import active_minutes, stats
from tutor.tests._cur import make_ctx

if TYPE_CHECKING:
    from pathlib import Path

T = 1_800_000_000.0


def _session(root: Path, name: str, learner_at: list[float]) -> None:
    body = {"message": "Q?", "low_effort": False, "check": None, "check_result": None}
    events: list[dict[str, Any]] = [
        {"type": "start", "card": "c", "t": T},
        {"type": "tutor", "t": T + 1, "turn": body},
    ]
    for at in learner_at:
        events += [
            {"type": "learner", "text": "an answer", "t": at, "msg_id": f"m{at}"},
            {"type": "tutor", "t": at + 1, "turn": body},
        ]
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(e) + "\n" for e in events)
    (root / "sessions" / f"{name}.jsonl").write_text(text, encoding="utf-8")


def test_active_minutes_sum_the_days_sessions(tmp_path: Path) -> None:
    assert active_minutes(tmp_path / "sessions", "2027-01-15") == 0
    _session(tmp_path, "20270115-080000-aaaa", [T + 100, T + 200, T + 300])
    _session(tmp_path, "20270115-090000-bbbb", [T + 150, T + 290])
    _session(tmp_path, "20270114-090000-cccc", [T + 250])  # another day
    _session(tmp_path, "20270115-nope", [T + 250])  # not a session id
    (tmp_path / "sessions" / "20270115-100000-dddd.jsonl").write_text(
        "", encoding="utf-8"
    )  # nothing resumable in it
    one = active_minutes(tmp_path / "sessions", "2027-01-15")
    assert one >= 7  # both sessions' engaged time counts, not just the newest
    assert active_minutes(tmp_path / "sessions", "2027-01-14") < one


def test_stats_today_carries_active_minutes(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    today = stats(ctx, minutes={})["today"]
    assert today["active_minutes"] == 0
