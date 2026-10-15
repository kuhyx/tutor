# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The drill's wrong options (``distractors``)."""

from __future__ import annotations

from tutor.cards import Card, Topic
from tutor.distractors import OPTIONS, options_for


def _card(cid: str, back: str, topic: str = "t", front: str = "front?") -> Card:
    return Card(cid, front, back, "https://x.org", "x", Topic(topic, topic, ("",)))


def test_closest_backs_win_over_topic() -> None:
    target = _card("c0", "a 4-byte floating point number", front="REAL type size?")
    pool = [
        target,
        _card("c1", "the watchdog aborts the task"),
        _card("c2", "INT is a 2-byte integer", "u", front="INT type size?"),
        _card("c3", "DINT is a 4-byte integer", "u", front="DINT type size?"),
        _card("c4", "LREAL: an 8-byte floating point number", "u"),
        _card("c5", "the rack holds modules"),
    ]
    shown, answer = options_for(target, pool, "seed")
    assert shown[answer] == target.back
    assert len(shown) == OPTIONS
    assert "the watchdog aborts the task" not in shown
    assert "the rack holds modules" not in shown


def test_ties_prefer_the_topic_and_skip_duplicates() -> None:
    target = _card("c0", "x", front="?")  # no content words: every score ties
    pool = [
        target,
        _card("c1", "near1", front="?"),
        _card("c2", "near2", front="?"),
        _card("c3", "x", front="?"),  # same text as the answer: never an option
        _card("c4", "near1", front="?"),  # duplicate text: once
        _card("c5", "far1", "u", front="?"),
        _card("c6", "far2", "u", front="?"),
    ]
    shown, answer = options_for(target, pool, "seed")
    assert shown[answer] == "x"
    assert {"near1", "near2"} <= set(shown)
    assert len(set(shown)) == len(shown) == OPTIONS
    assert options_for(target, pool, "seed") == (shown, answer)


def test_a_lone_card_and_wordless_cards() -> None:
    target = _card("c0", "ok", front="?")
    assert options_for(target, [target], "seed") == (["ok"], 0)
    shown, _ = options_for(target, [target, _card("c1", "no", front="!")], "s")
    assert sorted(shown) == ["no", "ok"]
