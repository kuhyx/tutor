# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Fold step 7: ``struggle(c)``, and its golden vectors (``DOCS-contract-struggle.md`` §3)."""

from __future__ import annotations

from tutor.curriculum import fsrs_vectors
from tutor.curriculum.fold import fold
from tutor.curriculum.fsrs_vectors import ALL as CASES
from tutor.curriculum.ids import ulid
from tutor.tests._cur import T0, D, H


def _ev(
    kind: str, at: int, dev: str = "a", n: int = 0, **extra: object
) -> dict[str, object]:
    return {
        "dev": dev,
        "eid": ulid(at, bytes([n] * 10)),
        "k": kind,
        "s": "car",
        "c": "x",
        "at": at,
        **extra,
    }


def _again(at: int, n: int, rev: int = 1, dev: str = "a") -> dict[str, object]:
    return _ev("review", at, dev, n, r=1, rev=rev)


TAUGHT = _ev("taught", T0, "pc", 99)


def test_three_agains_in_a_row() -> None:
    events = [TAUGHT, *(_again(T0 + i * D, i) for i in (1, 2, 3))]
    assert fold(events).card("car", "x").struggle(1) == 3


def test_a_good_or_hard_at_the_current_rev_ends_the_run() -> None:
    good = _ev("review", T0 + 3 * D, "a", 3, r=3, rev=1)
    events = [TAUGHT, _again(T0 + D, 1), _again(T0 + 2 * D, 2), good]
    assert fold([*events, _again(T0 + 4 * D, 4)]).card("car", "x").struggle(1) == 1
    hard = _ev("review", T0 + 3 * D, "a", 3, r=2, rev=1)
    assert fold([TAUGHT, _again(T0 + D, 1), hard]).card("car", "x").struggle(1) == 0


def test_only_reviews_at_the_current_rev_count() -> None:
    old = [TAUGHT, _again(T0 + D, 1), _again(T0 + 2 * D, 2)]
    assert fold(old).card("car", "x").struggle(2) == 0  # edited since
    newer = [*old, _again(T0 + 3 * D, 3, rev=2)]
    assert fold(newer).card("car", "x").struggle(2) == 1
    # A stale phone's Good at the old rev neither counts nor ends the run.
    stale = _ev("review", T0 + 4 * D, "b", 4, r=3, rev=1)
    late = [*newer, stale, _again(T0 + 5 * D, 5, rev=2)]
    assert fold(late).card("car", "x").struggle(2) == 2


def test_undo_dedupe_reteach_and_untaught_reset_or_skip() -> None:
    three = [TAUGHT, *(_again(T0 + i * D, i) for i in (1, 2, 3))]
    undo = _ev("review_undo", T0 + 3 * D + 5_000, "a", 9, of=three[-1]["eid"])
    assert fold([*three, undo]).card("car", "x").struggle(1) == 2
    twin = _again(T0 + 3 * D + 30_000, 8, dev="b")  # cross-device < 60 s
    assert fold([*three, twin]).card("car", "x").struggle(1) == 3
    again = _ev("taught", T0 + 4 * D, "pc", 98)
    assert fold([*three, again]).card("car", "x").struggle(1) == 0
    gone = _ev("untaught", T0 + 4 * D, "pc", 97)
    assert fold([*three, gone]).card("car", "x").struggle(1) == 0


def test_drill_picks_count_and_untaught_is_zero() -> None:
    drill = _ev("review", T0 + H, "a", 5, r=1, rev=1, src="drill")
    assert fold([TAUGHT, drill]).card("car", "x").struggle(1) == 1
    assert fold([_again(T0 + D, 1)]).card("car", "x").struggle(1) == 0
    assert fold([]).card("car", "x").struggle(1) == 0


def test_every_vector_pins_struggle() -> None:
    cases = {c["name"]: c for c in fsrs_vectors.build()}
    for vector in cases.values():
        for card, expect in vector["expect"].items():
            assert isinstance(expect["struggle"], int), (vector["name"], card)
    want = {
        "struggle: three Again ratings": 3,
        "struggle: Again, Again, Good, Again": 1,
        "struggle: Again at an old rev ignored after an edit": 1,
        "struggle: undo pops the last Again": 2,
        "struggle: cross-device Again within 60 s counts once": 2,
        "struggle: re-teach resets": 0,
        "struggle: drill picks count": 2,
        "struggle: Hard ends the run": 0,
    }
    assert {name: cases[name]["expect"]["x"]["struggle"] for name in want} == want
    assert set(want) <= set(CASES)
