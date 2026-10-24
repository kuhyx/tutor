# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Leftover seconds: a day pays its whole active minutes, not each card's.

kuhy, 2026-10-24: 12 cards of 31.2 active minutes paid 24, because each card
dropped its part minute. Quotas as in ``test_carry`` (Sat 10-24 / Sun 10-25 50).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from tutor import carry, leftover, resume
from tutor.clock import EngagementClock
from tutor.ledger_io import default_paths
from tutor.tests._fakes import FakeSession, turn
from tutor.tests.test_carry import at, own, rows
from tutor.tests.test_engine import make

if TYPE_CHECKING:
    from pathlib import Path

ANSWER = "the coil pulls the contact closed"
TURN = {"message": "Next?", "low_effort": False, "check": None}


def card(
    folder: Path, day: int, clock: str, seconds: float, carry_in: float | None = None
) -> Path:
    """A transcript of one on-time reply ``seconds`` after the tutor's question."""
    t0 = at(day, int(clock[:2]), int(clock[2:4]))
    start: dict[str, Any] = {"type": "start", "card": "c1", "t": t0}
    if carry_in is not None:
        start["carry_in"] = carry_in
    events = [
        start,
        {"type": "tutor", "t": t0, "turn": TURN},
        {"type": "learner", "t": t0 + seconds, "text": ANSWER, "msg_id": "1"},
        {"type": "tutor", "t": t0 + seconds, "turn": TURN},
    ]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"202610{day:02d}-{clock}-{clock[:4]}.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return path


def units(path: Path) -> int:
    """The minutes ``path``'s own clock released."""
    replayed = resume.replay(path)
    assert replayed is not None
    return len(replayed.unrecorded)


def leftover_rows() -> list[dict[str, Any]]:
    return [r for r in rows() if str(r["entry_id"]).startswith("leftover-")]


def test_a_seeded_clock_releases_its_first_minute_early() -> None:
    clock = EngagementClock(0.0, carry_in=30.0)
    clock.tutor_message(0.0)
    clock.user_reply(30.0, ANSWER, low_effort=False)
    assert [u.block for u in clock.ready_blocks()] == [1]
    assert clock.active_seconds == 30.0  # the seed is not active time


def test_two_ninety_second_cards_pay_three_minutes(tmp_path: Path) -> None:
    first = card(tmp_path, 24, "100000", 90)
    seed = leftover.seed(tmp_path, "20261024")
    assert seed == 30.0
    second = card(tmp_path, 24, "101000", 90, carry_in=seed)
    assert units(first) + units(second) == 3


def test_the_seed_is_the_days_part_minute_only(tmp_path: Path) -> None:
    card(tmp_path, 23, "100000", 50)  # another day: never seeds today
    card(tmp_path, 24, "100000", 100)
    card(tmp_path, 24, "101000", 100, carry_in=40.0)
    assert leftover.seed(tmp_path, "20261024") == 20.0  # 200 s: 3 min + 20 s
    assert leftover.seed(tmp_path, "20261025") == 0.0


def test_a_new_card_is_opened_with_the_days_leftover(tmp_path: Path) -> None:
    day = time.strftime("%Y%m%d")
    folder = tmp_path / "data" / "sessions"
    folder.mkdir(parents=True)
    t0 = time.time() - 600
    (folder / f"{day}-000000-aaaa.jsonl").write_text(
        "".join(
            json.dumps(e) + "\n"
            for e in [
                {"type": "start", "card": "c1", "t": t0},
                {"type": "tutor", "t": t0, "turn": TURN},
                {"type": "learner", "t": t0 + 90, "text": ANSWER, "msg_id": "1"},
                {"type": "tutor", "t": t0 + 90, "turn": TURN},
            ]
        ),
        encoding="utf-8",
    )
    engine = make(tmp_path, FakeSession(turn()))
    asyncio.run(engine.start())
    path = folder / f"{engine.session_id}.jsonl"
    start = json.loads(path.read_text().splitlines()[0])
    assert start["type"] == "start"
    assert start["carry_in"] == 30.0


def test_a_past_days_lost_minutes_are_paid_now_once(tmp_path: Path) -> None:
    card(tmp_path, 23, "100000", 90)
    card(tmp_path, 23, "101000", 90)  # 1 + 1 paid of 3
    assert leftover.pay(tmp_path, now=at(24, 12)) == 1
    [row] = leftover_rows()
    assert row["entry_id"] == "leftover-2026-10-23-m1"
    assert row["day"] == "2026-10-24"
    assert row["detail"]["minutes"] == 1
    assert row["detail"]["ended_at"] == at(24, 12)
    assert "carry" not in row["detail"]
    assert leftover.pay(tmp_path, now=at(24, 13)) == 0
    assert len(leftover_rows()) == 1


def test_today_counts_only_cards_that_can_no_longer_accrue(tmp_path: Path) -> None:
    card(tmp_path, 24, "100000", 162)  # 2.7 min, closed
    card(tmp_path, 24, "101000", 30)  # live: its part minute is still its own
    assert leftover.pay(tmp_path, now=at(24, 12)) == 0
    card(tmp_path, 24, "102000", 10)  # a new card closes the second
    assert leftover.pay(tmp_path, now=at(24, 12, 30)) == 1  # 192 s: 3 - (2 + 0)
    assert [r["entry_id"] for r in leftover_rows()] == ["leftover-2026-10-24-m1"]


def test_seeded_cards_owe_nothing(tmp_path: Path) -> None:
    card(tmp_path, 23, "100000", 90)
    card(tmp_path, 23, "101000", 90, carry_in=30.0)
    card(tmp_path, 23, "102000", 45, carry_in=0.0)
    assert leftover.pay(tmp_path, now=at(24, 12)) == 0


def test_back_pay_past_the_quota_is_banked_for_tomorrow(tmp_path: Path) -> None:
    own(24, 50)  # Saturday's quota met
    card(tmp_path, 23, "100000", 90)
    card(tmp_path, 23, "101000", 90)
    card(tmp_path, 23, "102000", 90)  # 3 of 4 paid: 1 lost
    leftover.pay(tmp_path, now=at(24, 12))
    assert carry.bank_now(at(24, 18)).banked == 1
    bank = carry.spend(now=at(25, 0, 1))
    assert bank is not None
    assert bank.prepaid == 1


def test_unresumable_and_foreign_files_are_skipped(tmp_path: Path) -> None:
    card(tmp_path, 23, "100000", 90)
    card(tmp_path, 23, "101000", 90)
    (tmp_path / "20261023-102000-cccc.jsonl").write_text(
        json.dumps({"type": "learner", "t": at(23)}) + "\n", encoding="utf-8"
    )
    (tmp_path / "20261023-notes.jsonl").write_text("{}\n", encoding="utf-8")
    assert leftover.owed(tmp_path, "20261023", live=False) == 1
    assert leftover.seed(tmp_path, "20261023") == 0.0


def test_a_later_larger_figure_pays_only_the_delta(tmp_path: Path) -> None:
    card(tmp_path, 24, "100000", 90)
    card(tmp_path, 24, "101000", 90)
    card(tmp_path, 24, "102000", 1)  # closes the second: 180 s, 2 paid
    assert leftover.pay(tmp_path, now=at(24, 12)) == 1
    card(tmp_path, 24, "103000", 90)  # closes the third and a fourth 90 s
    card(tmp_path, 24, "104000", 90)
    card(tmp_path, 24, "105000", 1)
    assert leftover.pay(tmp_path, now=at(24, 13)) == 1  # 361 s: 6 - 4 = 2 owed
    paid = [(r["entry_id"], r["detail"]["minutes"]) for r in leftover_rows()]
    assert paid == [("leftover-2026-10-24-m1", 1), ("leftover-2026-10-24-m2", 1)]


def test_an_unreadable_ledger_pays_nothing_and_raises_nothing(
    tmp_path: Path,
) -> None:
    card(tmp_path, 23, "100000", 90)
    card(tmp_path, 23, "101000", 90)
    ledger = default_paths().ledger
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("not json", encoding="utf-8")
    assert leftover.pay(tmp_path, now=at(24, 12)) == 0


def test_named_days_only_are_paid(tmp_path: Path) -> None:
    for day in (22, 23):
        card(tmp_path, day, "100000", 90)
        card(tmp_path, day, "101000", 90)
    assert leftover.pay(tmp_path, now=at(24, 12), days=["20261023"]) == 1
    assert [r["entry_id"] for r in leftover_rows()] == ["leftover-2026-10-23-m1"]
