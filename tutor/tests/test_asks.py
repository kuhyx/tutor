# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One thing per question: an entry holding two questions becomes two.

2026-10-17: one box asked two things at once, so one answer field had to
carry both replies. The rules forbid it; :func:`asks.split` is the net.
"""

from __future__ import annotations

import pytest

from tutor import asks

FIRST = (
    "Czym różni się wskazanie na nazwę serwera (np. www-virt12) od wskazania na "
    "adres IP?"  # codespell:ignore adres
)
SECOND = "Co się dzieje, gdy adres IP serwera się zmienia?"  # codespell:ignore adres
LIVE = f"{FIRST} {SECOND}"  # live session 2026-10-17


@pytest.mark.parametrize(
    ("said", "parts"),
    [
        (LIVE, [FIRST, SECOND]),
        ("Lead-in. Q1? Q2?", ["Lead-in. Q1?", "Q2?"]),
        ("A?\nB? C?", ["A?", "B?", "C?"]),
        ("A? B? Explain.", ["A?", "B? Explain."]),
        ("What is a PLC?", ["What is a PLC?"]),
        ("Why? Explain it.", ["Why? Explain it."]),
        ("What is `a ? b : c`? Say it.", ["What is `a ? b : c`? Say it."]),
        ("Open https://x.org/?a=1 and why?", ["Open https://x.org/?a=1 and why?"]),
        ('He asked "why?" and what?', ['He asked "why?" and what?']),
        ("Q1?  Q2?  ", ["Q1?", "Q2?"]),
        ("No question here.", ["No question here."]),
    ],
    ids=[
        "live",
        "lead-in",
        "newline",
        "tail",
        "one",
        "one-then-task",
        "code",
        "url",
        "quoted",
        "trailing-space",
        "none",
    ],
)
def test_entry_splits_per_question(said: str, parts: list[str]) -> None:
    assert asks.entry(said) == parts


def test_split_keeps_choices_on_unsplit_neighbours() -> None:
    three = ["a", "b", "c"]
    other = ["x", "y", "z"]
    said, raw = asks.split(["One?", LIVE, "Two?"], [three, ["p", "q", "r"], other])
    assert said == ["One?", *asks.entry(LIVE), "Two?"]
    assert raw == [three, None, None, other]


@pytest.mark.parametrize("raw", [None, "junk", [["a", "b", "c"]]])
def test_split_tolerates_missing_or_short_choices(raw: object) -> None:
    said, aligned = asks.split(["A? B?", "C?"], raw)
    assert said == ["A?", "B?", "C?"]
    assert aligned == [None, None, None]


def test_split_passes_one_question_entries_through() -> None:
    assert asks.split(["A?"], (["a", "b", "c"],)) == (["A?"], [["a", "b", "c"]])
