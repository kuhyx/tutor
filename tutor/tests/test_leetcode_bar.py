# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The LeetCode bar's session map (``DOCS-contract-leetcode-bar.md``): display only.

A session is a LeetCode theory session when the guard's signed phase is
``theory`` and the session's card is in a listed (subject, module). Its
numbers come from the guard's loopback route; a number the guard could not
give is left out, never 0.
"""

from __future__ import annotations

import functools
import http.client
import logging
from typing import TYPE_CHECKING, Any

import pytest

from tutor import ledger_pay, leetcode_bar, unit_credit
from tutor.tests._cur import T0, card, make_ctx, module, subject, taught
from tutor.tests._guard_theory import GuardFake, theory
from tutor.tests._phase import LC, SQL, grant, phase_row, write_phase

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

AT = T0 / 1000
LOCAL = {"unit": "a", "taught": 1, "total": 2, "full": False}
NUMBERS = {"into": 7, "per_credit": 12, "credits": 0, "needed": 7}
_LOGGER = "tutor.leetcode_bar"


def _ctx(tmp_path: Path, name: str = LC) -> Context:
    ctx, _ = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {
        "a0": card("a", 0),
        "a1": card("a", 1),
        "a2": card("a", 2, suspended=True),
        "b0": card("b", 0),
    }
    subject(ctx, name, modules=mods, found=found)
    taught(ctx, name, "a0", T0)
    taught(ctx, name, "b0", T0, eid_n=1)  # another module: not counted
    return ctx


def _bar(ctx: Context, card_id: str = "a1", name: str = LC) -> dict[str, Any] | None:
    return leetcode_bar.session_map(ctx, name, card_id, AT)


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == _LOGGER and r.levelno >= logging.WARNING
    ]


def test_a_theory_session_gets_the_whole_map(
    tmp_path: Path, guard_theory: GuardFake
) -> None:
    grant((LC, "a"))
    assert _bar(_ctx(tmp_path)) == LOCAL | NUMBERS
    assert guard_theory.timeouts == [0.5]


@pytest.mark.parametrize("card_id", ["a0", "a1"], ids=["taught", "untaught"])
def test_any_card_of_a_listed_module_is_a_theory_session(
    tmp_path: Path, card_id: str
) -> None:
    grant((LC, "a"))
    bar = _bar(_ctx(tmp_path), card_id)
    assert bar is not None
    assert (bar["taught"], bar["total"]) == (1, 2)  # a suspended card is not counted


def test_no_phase_file_is_no_bar_and_no_call(
    tmp_path: Path, guard_theory: GuardFake
) -> None:
    assert _bar(_ctx(tmp_path)) is None
    assert guard_theory.timeouts == []


@pytest.mark.parametrize(
    ("row", "card_id", "name"),
    [
        (phase_row([(LC, "b")]), "a1", LC),  # another module is listed
        (phase_row([]), "a1", LC),  # theory with nothing listed
        (phase_row([], phase="solve"), "a1", LC),
        (phase_row([(LC, "a")]) | {"hmac": "0" * 64}, "a1", LC),  # unverifiable
        (phase_row([(SQL, "a")]), "a1", SQL),  # listed, but not a LeetCode subject
        (phase_row([(LC, "a")]), "nope", LC),  # not a card of the subject
    ],
    ids=["other-module", "empty", "solve", "forged", "ungated", "unknown-card"],
)
def test_anything_else_is_no_bar_and_no_call(
    tmp_path: Path,
    guard_theory: GuardFake,
    row: dict[str, Any],
    card_id: str,
    name: str,
) -> None:
    write_phase(row)
    assert _bar(_ctx(tmp_path, name), card_id, name) is None
    assert guard_theory.timeouts == []


def test_a_subject_without_cards_is_no_bar(tmp_path: Path) -> None:
    grant((LC, "a"))
    ctx, _ = make_ctx(tmp_path)
    assert leetcode_bar.session_map(ctx, LC, "a1", AT) is None


def test_full_once_today_reached_the_daily_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    grant((LC, "a"))
    ctx = _ctx(tmp_path)
    cap = ledger_pay.DAILY_CAP_MINUTES
    asked: list[object] = []

    def today(_at: float, kinds: object, m: int) -> int:
        asked.append(kinds)
        return m

    for minutes, want in ((cap - 1, False), (cap, True), (cap + 5, True)):
        monkeypatch.setattr(
            unit_credit, "ledger_minutes_today", functools.partial(today, m=minutes)
        )
        bar = _bar(ctx)
        assert bar is not None
        assert bar["full"] is want
    assert asked == [{ledger_pay.LC_CREDIT}] * 3  # the LC kind's own cap


@pytest.mark.parametrize(
    "reply",
    [
        OSError("refused"),
        TimeoutError("slow"),
        http.client.BadStatusLine("garbage"),  # a reply that is not HTTP
        http.client.IncompleteRead(b"{", 40),  # shorter than Content-Length
        500,
        b"not json {",
        b"[1, 2]",
        b'{"theory": "x"}',
        theory(checked=False),
        theory(day="2027-01-14"),  # yesterday's answer
        theory(day=None),
        theory(unit="other"),  # numbers of another unit
        theory(phase="solve"),
    ],
    ids=[
        "down",
        "timeout",
        "bad-status-line",
        "incomplete-read",
        "http-500",
        "bad-json",
        "list",
        "not-a-map",
        "unchecked",
        "stale-day",
        "no-day",
        "other-unit",
        "other-phase",
    ],
)
def test_could_not_check_leaves_every_number_out(
    tmp_path: Path, guard_theory: GuardFake, reply: Any
) -> None:
    grant((LC, "a"))
    guard_theory.reply = reply
    assert _bar(_ctx(tmp_path)) == LOCAL


def test_a_non_200_answer_leaves_the_numbers_out(
    tmp_path: Path, guard_theory: GuardFake
) -> None:
    grant((LC, "a"))
    guard_theory.status = 204
    assert _bar(_ctx(tmp_path)) == LOCAL


@pytest.mark.parametrize(
    ("field", "key"),
    [
        ("minutes_into_credit", "into"),
        ("minutes_per_credit", "per_credit"),
        ("credits_today", "credits"),
        ("needed", "needed"),
    ],
)
@pytest.mark.parametrize("bad", [None, True, "7", -1, 1.5], ids=str)
def test_one_unreadable_number_is_the_only_one_left_out(
    tmp_path: Path, guard_theory: GuardFake, field: str, key: str, bad: object
) -> None:
    grant((LC, "a"))
    guard_theory.reply = theory(**{field: bad})
    assert _bar(_ctx(tmp_path)) == LOCAL | {
        k: v for k, v in NUMBERS.items() if k != key
    }


def test_zero_is_a_number(tmp_path: Path, guard_theory: GuardFake) -> None:
    grant((LC, "a"))
    guard_theory.reply = theory(minutes_into_credit=0, credits_today=0, needed=0)
    bar = _bar(_ctx(tmp_path))
    assert bar is not None
    assert (bar["into"], bar["credits"], bar["needed"]) == (0, 0, 0)
