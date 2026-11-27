# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A LeetCode subject's minutes pay LeetCode time only, never tutor time.

kuhy, 2026-11-27: "Doing leetcode in tutor whether it is learning modules or
repeating anki cards should NOT grant tutor time only leetcode time". Two
paths still wrote ``credit`` for a GATED subject: a review whose card no longer
names a module, and the leftover top-up, which summed every card of the day.
"""

from __future__ import annotations

from datetime import datetime
import json
import time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest

from tutor import anki, leftover, review_credit
from tutor.anki_collection import COLLECTION_ENV
from tutor.curriculum.theory_phase import GATED
from tutor.ledger_pay import CREDIT, LC_CREDIT
from tutor.tests._anki_support import LC_CARD, LC_SUB_CARD, append, make_collection
from tutor.tests._relay_support import PHONE, WORKER, engine
from tutor.tests._review_support import NOW, at, log_of, rev
from tutor.tests.test_anki import window
from tutor.tests.test_carry import rows
from tutor.tests.test_leftover import ANSWER, TURN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

LC = min(GATED)
TODAY = f"review-20261015-{PHONE}"


@pytest.fixture(autouse=True)
def _warsaw(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Local time is Warsaw for the test, and whatever it was afterwards."""
    with monkeypatch.context() as patch:
        patch.setenv("TZ", "Europe/Warsaw")
        time.tzset()
        yield
    time.tzset()


def _row(entry: str) -> dict[str, Any]:
    [found] = [r for r in rows() if r["entry_id"] == entry]
    return found


def test_an_untagged_review_of_a_leetcode_card_pays_leetcode_time(
    tmp_path: Path,
) -> None:
    eng, _ = engine(tmp_path)
    gated = rev(PHONE, at(15, 10, 1, 0), 60_000, card="gone-card")
    gated["s"] = LC
    log_of(tmp_path, [gated])
    review_credit.credit_now(eng.ctx, NOW)
    row = _row(f"{TODAY}-m1")
    assert row["kind"] == LC_CREDIT
    assert row["detail"]["subject"] == LC
    assert "module" not in row["detail"]  # nothing the guard could count


def test_an_untagged_review_of_another_subject_still_pays_tutor_time(
    tmp_path: Path,
) -> None:
    eng, _ = engine(tmp_path)
    log_of(tmp_path, [rev(PHONE, at(15, 10, 1, 0), 60_000, card="gone-card")])
    review_credit.credit_now(eng.ctx, NOW)
    row = _row(f"{TODAY}-m1")
    assert row["kind"] == CREDIT
    assert "subject" not in row["detail"]


def nov(day: int, hour: int, minute: int = 0) -> float:
    """Unix time of 2026-11-``day`` ``hour``:``minute`` in Warsaw."""
    return datetime(
        2026, 11, day, hour, minute, tzinfo=ZoneInfo("Europe/Warsaw")
    ).timestamp()


def _card(
    folder: Path,
    clock: str,
    seconds: float,
    subject: str | None,
    day: str = "20261125",
) -> None:
    """A ``day`` transcript on ``subject``: one reply after ``seconds``."""
    when = datetime.strptime(day + clock, "%Y%m%d%H%M%S").replace(
        tzinfo=ZoneInfo("Europe/Warsaw")
    )
    t0 = when.timestamp()
    start: dict[str, Any] = {"type": "start", "card": "c1", "t": t0}
    start |= {"subject": subject} if subject else {}
    events = [
        start,
        {"type": "tutor", "t": t0, "turn": TURN},
        {"type": "learner", "t": t0 + seconds, "text": ANSWER, "msg_id": "1"},
        {"type": "tutor", "t": t0 + seconds, "turn": TURN},
    ]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{day}-{clock}-{clock[:4]}.jsonl"
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def test_leftover_never_tops_up_a_leetcode_cards_part_minutes(tmp_path: Path) -> None:
    _card(tmp_path, "100000", 90, LC)
    _card(tmp_path, "101000", 90, LC)  # 3 whole minutes, 2 paid: LeetCode's
    assert leftover.pay(tmp_path, now=nov(26, 12)) == 0
    _card(tmp_path, "102000", 90, "car")
    _card(tmp_path, "103000", 90, None)  # pre-curriculum: tutor time
    assert leftover.pay(tmp_path, now=nov(26, 13)) == 1  # only the tutor pair's
    assert [r["kind"] for r in rows() if "leftover" in r["entry_id"]] == [CREDIT]


def test_a_day_before_the_split_keeps_its_old_sum(tmp_path: Path) -> None:
    """kuhy: nothing changes for what was written before 2026-11-23."""
    _card(tmp_path, "100000", 90, LC, day="20261122")
    _card(tmp_path, "101000", 90, LC, day="20261122")
    assert leftover.owed(tmp_path, "20261122", live=False) == 1
    assert leftover.seed(tmp_path, "20261122", LC) == 0.0  # no LeetCode pool


def test_a_card_is_seeded_from_its_own_kinds_part_minutes(tmp_path: Path) -> None:
    _card(tmp_path, "100000", 90, LC)  # 30 s LeetCode part minute
    _card(tmp_path, "101000", 80, "car")  # 20 s tutor part minute
    assert leftover.seed(tmp_path, "20261125", LC) == 30.0
    assert leftover.seed(tmp_path, "20261125", "car") == 20.0
    assert leftover.seed(tmp_path, "20261125", None) == 20.0


def test_a_new_leetcode_card_opens_with_the_leetcode_part_minute(
    tmp_path: Path,
) -> None:
    eng, _ = engine(tmp_path)
    folder = tmp_path / "data" / "sessions"
    folder.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y%m%d")
    t0 = time.time() - 600
    for clock, seconds, subject in (("000000", 90, LC), ("000100", 80, "car")):
        start = {"type": "start", "card": "c1", "t": t0, "subject": subject}
        events = [
            start,
            {"type": "tutor", "t": t0, "turn": TURN},
            {"type": "learner", "t": t0 + seconds, "text": ANSWER, "msg_id": "1"},
            {"type": "tutor", "t": t0 + seconds, "turn": TURN},
        ]
        (folder / f"{day}-{clock}-aaaa.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in events), encoding="utf-8"
        )
    _, start = eng._opening(f"{day}-000200-bbbb", "c1", LC)
    assert start["carry_in"] == 30.0


def test_anki_reviews_of_the_leetcode_deck_pay_no_tutor_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "anki/collection.anki2"
    monkeypatch.setenv(COLLECTION_ENV, str(path))
    noon = datetime(2026, 11, 27, 12, 0, tzinfo=ZoneInfo("Europe/Warsaw")).timestamp()
    window(noon - 3600, noon + 3600)
    make_collection(path, [(int((noon - 60) * 1000), 90_000, 1)], keep_wal=True)
    for card, at_s in ((LC_CARD, 50), (LC_SUB_CARD, 40)):
        append(path, [(int((noon - at_s) * 1000), 600_000, 1)], card)
    append(path, [(int((noon - 30) * 1000), 60_000, 1)], 4)  # "LeetCodeX": not it
    assert anki.credit_pass(noon).eligible_min == 2  # 90 s + 60 s, no LeetCode


def test_a_gone_leetcode_card_gets_no_endless_module_less_twin(
    tmp_path: Path,
) -> None:
    eng, _ = engine(tmp_path)
    gated = rev(PHONE, at(15, 10, 1, 0), 60_000, card="gone-card")
    gated["s"] = LC
    log_of(tmp_path, [gated])
    review_credit.credit_pass(eng.ctx.log, WORKER, NOW)  # untagged, as before C1
    before = rows()
    for _ in range(2):
        review_credit.credit_now(eng.ctx, NOW)
    assert rows() == before
