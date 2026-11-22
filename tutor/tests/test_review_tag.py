# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A review minute's ledger row names its subject and module (contract C1).

leetcode-guard pays one LeetCode credit per 12 signed tutor minutes of a
module and reads only rows signing ``detail.subject`` and ``detail.module``.
Review rows carry them too, plus ``activity: "review"``; today's rows written
before that are re-signed as twins of the same ``entry_id``, which every
ledger reader pays once, so the minutes paid never change.
"""

from __future__ import annotations

from datetime import date
import logging
import time
from typing import TYPE_CHECKING, Any

import earned_time
import pytest

from tutor import carry, credit, ledger_pay, progress, review_credit, unit_credit
from tutor.clock import BlockReady
from tutor.ledger_io import default_paths, read_key, read_rows
from tutor.tests._credit_support import put
from tutor.tests._relay_support import PHONE, WORKER, engine
from tutor.tests._review_support import (
    NOW,
    at,
    ledger_entries,
    log_of,
    plant_cards,
    rev,
    review_rows,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from tutor.curriculum.context import Context

TAGS = {"subject", "module", "activity"}
TODAY = f"review-20261015-{PHONE}"
YESTERDAY = f"review-20261014-{PHONE}"
CARDS = {"a-1": "mod-a", "a-2": "mod-b", "a-3": "mod-c"}


@pytest.fixture(autouse=True)
def _warsaw(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Local time is Warsaw for the test, and whatever it was afterwards."""
    monkeypatch.setenv("TZ", "Europe/Warsaw")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def _ctx(tmp_path: Path, cards: dict[str, str] | None = None) -> Context:
    """The worker's context on ``tmp_path/data``, subject ``car`` holding ``cards``."""
    eng, _ = engine(tmp_path)
    if cards:
        plant_cards(tmp_path / "data", "car", cards)
    return eng.ctx


def _minute(n: int, card: str, day: int = 15) -> dict[str, Any]:
    """A phone review of ``card`` that ends the ``n``-th minute of ``day``."""
    return rev(PHONE, at(day, 10, n, 0), 60_000, card=card)


def _day_log(day: int) -> list[dict[str, Any]]:
    """Eight one-minute reviews on ``day``, cards a-1, a-2, a-3 in turn."""
    return [_minute(n, f"a-{n % 3 + 1}", day) for n in range(1, 9)]


def test_a_review_minute_row_carries_subject_module_and_activity(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path, CARDS)
    log = log_of(tmp_path, [_minute(1, "a-1")])
    review_credit.credit_now(ctx, NOW)
    first = review_rows()[f"{TODAY}-m1"]["detail"]
    assert first["subject"] == "car"
    assert first["module"] == "mod-a"
    assert first["activity"] == "review"
    log.append([_minute(2, "a-2")])  # the review that completes minute 2
    review_credit.credit_now(ctx, NOW + 60)
    second = review_rows()[f"{TODAY}-m2"]["detail"]
    assert (second["subject"], second["module"]) == ("car", "mod-b")
    assert second["ended_at"] == at(15, 10, 2, 0) / 1000  # the same event
    assert second["minutes"] == 1
    assert set(second) - TAGS == set(first) - TAGS  # nothing else was added


def test_a_span_is_tagged_by_the_review_that_ended_its_last_minute(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path, CARDS)
    log_of(tmp_path, [_minute(1, "a-1"), _minute(2, "a-2"), _minute(3, "a-3")])
    review_credit.credit_now(ctx, NOW)
    detail = review_rows()[f"{TODAY}-m3"]["detail"]
    assert (detail["minutes"], detail["module"]) == (3, "mod-c")


def test_a_review_whose_card_or_subject_is_gone_is_untagged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx = _ctx(tmp_path, CARDS)
    log_of(tmp_path, [_minute(1, "deleted-card")])
    with caplog.at_level(logging.WARNING, logger="tutor.review_credit"):
        review_credit.credit_now(ctx, NOW)
    detail = review_rows()[f"{TODAY}-m1"]["detail"]
    assert detail["minutes"] == 1
    assert not TAGS & set(detail)
    assert "deleted-card" in caplog.text
    gone = rev(PHONE, at(15, 11, 1, 0), 60_000)
    gone["s"] = "no-such-subject"
    ctx.log.append([gone])
    review_credit.credit_now(ctx, NOW + 60)
    assert not TAGS & set(review_rows()[f"review-20261015-{PHONE}-m2"]["detail"])


def test_a_lesson_row_never_gets_an_activity_key() -> None:
    unit_credit.credit_units(
        [BlockReady(1, 60.5, NOW, 0, 0)],
        "s-lesson",
        now=NOW,
        taught=ledger_pay.Taught(subject="car", module="mod-a"),
    )
    detail = ledger_entries()[0]["detail"]
    assert (detail["subject"], detail["module"]) == ("car", "mod-a")
    assert "activity" not in detail


def _before_the_tags(tmp_path: Path) -> tuple[Context, list[dict[str, Any]]]:
    """Today's and yesterday's review rows as the writer made them untagged."""
    ctx = _ctx(tmp_path, CARDS)
    log = log_of(tmp_path, [*_day_log(15), *_day_log(14)])
    review_credit.credit_pass(log, WORKER, NOW)  # no card lookup: untagged rows
    assert not any(TAGS & set(r["detail"]) for r in ledger_entries())
    return ctx, ledger_entries()


def test_todays_untagged_review_rows_get_a_tagged_twin(tmp_path: Path) -> None:
    ctx, before = _before_the_tags(tmp_path)
    review_credit.credit_now(ctx, NOW)
    after = ledger_entries()
    assert after[: len(before)] == before  # the untagged originals stay
    twins = after[len(before) :]
    assert [t["entry_id"] for t in twins] == [f"{TODAY}-m8"]  # one span of 8 minutes
    original, twin = next(r for r in before if r["entry_id"] == f"{TODAY}-m8"), twins[0]
    assert twin["detail"]["module"] == "mod-c"  # a-3 ended minute 8
    assert {k: v for k, v in twin["detail"].items() if k not in TAGS} == original[
        "detail"
    ]
    assert twin["detail"]["activity"] == "review"
    assert {k: v for k, v in twin.items() if k not in {"detail", "hmac"}} == {
        k: v for k, v in original.items() if k not in {"detail", "hmac"}
    }
    assert earned_time.verified(twin, credit_key())
    assert not any(r["entry_id"].startswith(YESTERDAY) for r in twins)  # today only


def credit_key() -> bytes:
    """The test ledger's signing key."""
    key = read_key(default_paths().key_file)
    assert key is not None
    return key


def test_the_backfill_runs_once_and_by_itself(tmp_path: Path) -> None:
    ctx, _ = _before_the_tags(tmp_path)
    review_credit.credit_now(ctx, NOW)
    settled = default_paths().ledger.read_bytes()
    review_credit.credit_now(ctx, NOW + 60)
    review_credit.credit_now(ctx, NOW + 120)
    assert default_paths().ledger.read_bytes() == settled  # nothing more to write


def _paid(day: str) -> dict[str, object]:
    """Every figure the tutor and the earner derive from the ledger for ``day``."""
    where = default_paths()
    key = credit_key()
    paying = ledger_pay.paying(read_rows(where.ledger), key)
    lo, hi = credit.local_day(NOW)[1:]
    return {
        "paying": paying,
        "today": ledger_pay.minutes_between(paying, lo, hi),
        "unit_credit": unit_credit.ledger_minutes_today(NOW),
        "by_day": progress.ledger_minutes_by_day(),
        "bank": carry.bank_now(NOW),
        "session": credit.session_minutes(f"review-{day.replace('-', '')}-{PHONE}"),
        "earner": earned_time.credit_units(
            earned_time.TUTOR, where.ledger, where.key_file, date.fromisoformat(day)
        ),
    }


def test_paid_minutes_before_equal_paid_minutes_after_the_backfill(
    tmp_path: Path,
) -> None:
    """A ledger shaped like today's: lessons, reviews, a legacy block, Anki."""
    ctx, _ = _before_the_tags(tmp_path)
    lesson = [BlockReady(n, 60.5 * n, NOW - 600, 0, 0) for n in (1, 2, 3)]
    unit_credit.credit_units(lesson, "s-lesson", now=NOW - 600)
    anki = credit.credit_span(
        BlockReady(2, 120.0, NOW - 300, 0, 0), 2, "anki-20261015", now=NOW
    )
    assert anki.recorded
    before = _paid("2026-10-15")
    assert before["today"] == 3 + 8 + 2  # nothing is capped away
    assert before["earner"]
    review_credit.credit_now(ctx, NOW)
    twins = [r for r in ledger_entries() if r["detail"].get("activity") == "review"]
    assert len(twins) == 1
    assert _paid("2026-10-15") == before
    put(
        default_paths(),
        [r for r in ledger_entries() if r["detail"].get("activity") != "review"],
    )
    assert _paid("2026-10-15") == before  # with the twin gone it is the same


def test_only_genuine_review_rows_are_re_signed(tmp_path: Path) -> None:
    ctx, before = _before_the_tags(tmp_path)
    real = next(r for r in before if r["entry_id"] == f"{TODAY}-m8")
    stale = {**real["detail"], "ended_at": at(15, 10, 5, 0) / 1000, "minutes": 9}
    forged = {**real, "entry_id": f"{TODAY}-m5", "detail": stale}  # hmac is m8's
    anki = credit.credit_span(
        BlockReady(1, 60.0, NOW - 300, 0, 0), 1, "anki-20261015", now=NOW
    )
    assert anki.recorded
    put(default_paths(), [*ledger_entries(), forged])
    count = len(ledger_entries())
    review_credit.credit_now(ctx, NOW)
    new = ledger_entries()[count:]
    assert [r["entry_id"] for r in new] == [f"{TODAY}-m8"]  # not forged, not Anki


def test_a_row_that_does_not_end_at_its_review_is_not_tagged(tmp_path: Path) -> None:
    """The tag is the review that ended the minute; a row elsewhere stays as is."""
    ctx, before = _before_the_tags(tmp_path)
    real = next(r for r in before if r["entry_id"] == f"{TODAY}-m8")
    moved = {**real["detail"], "ended_at": real["detail"]["ended_at"] + 1}
    body = {k: v for k, v in real.items() if k != "hmac"} | {"detail": moved}
    resigned = body | {"hmac": earned_time.entry_signature(body, credit_key())}
    put(default_paths(), [*(r for r in before if r is not real), resigned])
    review_credit.credit_now(ctx, NOW)
    assert len(ledger_entries()) == len(before)
