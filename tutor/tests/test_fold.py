# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The fold: dedupe, teach/untaught/review/flag, FSRS, and the golden vectors."""

from __future__ import annotations

import json
import runpy
import sys
from typing import TYPE_CHECKING

import fsrs

from tutor.curriculum import fsrs_vectors
from tutor.curriculum.fold import (
    SCHEDULER,
    CardFold,
    fold,
    to_dt,
    to_ms,
    undone_eids,
)
from tutor.curriculum.ids import ulid
from tutor.tests._cur import T0, D

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


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


def test_ms_conversion_is_exact() -> None:
    assert to_ms(to_dt(1_791_800_000_123)) == 1_791_800_000_123


def test_taught_is_good_at_taught_time() -> None:
    folded = fold([_ev("taught", T0, session="s1")])
    state = folded.card("car", "x")
    expected, _ = SCHEDULER.review_card(
        fsrs.Card(card_id=1, due=to_dt(T0)), fsrs.Rating.Good, to_dt(T0)
    )
    assert state.taught
    assert state.session == "s1"
    assert state.reviews == []
    assert state.new_at == [T0]
    assert state.fsrs_state() == {
        "due": to_ms(expected.due),
        "stability": expected.stability,
        "difficulty": expected.difficulty,
        "state": "review",
    }
    assert folded.taught_ids("car") == {"x"}
    assert folded.taught_ids("other") == set()


def test_untouched_card_is_untaught() -> None:
    state = fold([]).card("car", "nope")
    assert state == CardFold()
    assert state.fsrs_state() is None


def test_dedupe_window_is_strictly_under_60s() -> None:
    events = [
        _ev("taught", T0),
        _ev("review", T0 + D, "a", 1, r=3),
        _ev("review", T0 + D + 59_999, "b", 2, r=1),
        _ev("review", T0 + D + 60_000, "b", 3, r=1),
        _ev("review", T0 + D + 120_000, "a", 4, r=2),
    ]
    folded = fold(events)
    assert folded.dropped == [events[2]["eid"]]
    assert [r for _, r in folded.card("car", "x").reviews] == [3, 1, 2]


def test_untaught_and_ignored_reviews_and_retaught() -> None:
    events = [
        _ev("review", T0, n=1, r=3),
        _ev("taught", T0 + 1),
        _ev("untaught", T0 + 2),
        _ev("review", T0 + 3, n=2, r=3),
        _ev("taught", T0 + 4),
        _ev("taught", T0 + 5),
    ]
    folded = fold(events)
    state = folded.card("car", "x")
    assert folded.ignored == [events[0]["eid"], events[3]["eid"]]
    assert state.new_at == [T0 + 1, T0 + 4]  # the third re-teaches: not new
    assert state.taught_at == T0 + 5


def test_flags_match_by_rev() -> None:
    state = fold([_ev("flag", T0, rev=2, reason="")]).card("car", "x")
    assert state.flagged(2)
    assert not state.flagged(3)


def test_an_undone_review_is_ignored_entirely() -> None:
    taught = _ev("taught", T0, "pc")
    wrong = _ev("review", T0 + D, "a", 1, r=3)
    undo = _ev("review_undo", T0 + D + 5_000, "a", 2, of=wrong["eid"])
    again = _ev("review", T0 + D + 10_000, "b", 3, r=1)  # the re-rate, other phone
    folded = fold([again, undo, wrong, taught])
    plain = fold([taught, again])
    state = folded.card("car", "x")
    assert state.reviews == [(T0 + D + 10_000, 1)]
    assert state.fsrs_state() == plain.card("car", "x").fsrs_state()
    assert not state.app_good  # the undone Good never counted
    assert folded.undone == [wrong["eid"]]
    assert folded.dropped == []  # an undone review never dedupes the re-rate
    assert wrong not in folded.kept
    assert undo in folded.kept


def test_an_undo_of_an_unknown_or_non_review_eid_is_a_no_op() -> None:
    taught = _ev("taught", T0, "pc")
    good = _ev("review", T0 + D, "a", 1, r=3)
    events = [
        taught,
        good,
        _ev("review_undo", T0 + D + 1, "a", 2, of=ulid(T0, b"\x09" * 10)),
        _ev("review_undo", T0 + D + 2, "a", 3, of=taught["eid"]),
    ]
    folded = fold(events)
    assert folded.card("car", "x").taught
    assert folded.card("car", "x").app_good
    assert (
        folded.card("car", "x").fsrs_state()
        == fold(events[:2]).card("car", "x").fsrs_state()
    )
    assert folded.undone == []


def test_global_events_fold_into_the_cap_and_lifted_days() -> None:
    def glob(kind: str, at: int, seq: int, **extra: object) -> dict[str, object]:
        eid = ulid(at, bytes([seq] * 10))
        return {"dev": "a", "eid": eid, "k": kind, "at": at, **extra}

    folded = fold(
        [
            glob("new_cap", T0 + 2, 1, n=40),
            glob("new_cap", T0 + 1, 2, n=12),
            glob("cap_lift", T0, 3, day="2027-01-15"),
            glob("cap_lift", T0 + D, 4, day="2027-01-16"),
        ]
    )
    assert folded.new_cap == 40  # the latest by ``at``
    assert folded.lifted_days == {"2027-01-15", "2027-01-16"}
    assert folded.cards == {}
    assert fold([]).new_cap is None
    assert undone_eids([_ev("review_undo", T0, of="E1"), _ev("review", T0)]) == {"E1"}


def test_vectors_file_matches_the_generator() -> None:
    on_disk = json.loads(fsrs_vectors.OUT.read_text(encoding="utf-8"))
    assert on_disk == fsrs_vectors.build()
    assert fsrs_vectors.render() == fsrs_vectors.OUT.read_text(encoding="utf-8")
    assert len(on_disk) >= 12
    names = {c["name"] for c in on_disk}
    assert "cross-device within 60 s: second dropped" in names
    dropped = next(c for c in on_disk if c["name"].startswith("cross-device within"))
    assert len(dropped["dropped"]) == 1


def test_vectors_script_writes_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "v" / "vectors.json"
    monkeypatch.setenv("TUTOR_VECTORS_OUT", str(out))
    monkeypatch.delitem(sys.modules, "tutor.curriculum.fsrs_vectors", raising=False)
    runpy.run_module("tutor.curriculum.fsrs_vectors", run_name="__main__")
    assert out.read_text(encoding="utf-8") == fsrs_vectors.render()
