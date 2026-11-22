# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A lesson on a rework card sees kuhy's own attempts on its problem; others do not."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from tutor import rework_context
from tutor.cards import Card, Topic
from tutor.prompt import for_source, system_prompt

if TYPE_CHECKING:
    from tutor.curriculum.source import CardSource

TOPIC = Topic(stem="hashing", title="Hashing", prefixes=("hashing",))
HEAD = "# kuhy's own attempts on this problem"


def _card(source: str) -> Card:
    return Card(
        id="hashing-map",
        front="Which lookup is O(1)?",
        back="A hash map.",
        source=source,
        excerpt="Rework of two-sum: Which lookup is O(1); A hash map.",
        topic=TOPIC,
    )


def _src(card: Card) -> CardSource:
    fake: Any = SimpleNamespace(
        subject="lc",
        profile=None,
        cards=lambda: [card],
        path=lambda cid: None,
        mastered=list,
    )
    return cast("CardSource", fake)


@pytest.fixture
def history() -> None:
    path = rework_context.guard_dir() / "history" / "two-sum.json"
    path.parent.mkdir(parents=True)
    rows = [{"status": "Wrong Answer", "lang": "python3", "timestamp": 1}]
    path.write_text(json.dumps({"submissions": rows}), encoding="utf-8")


@pytest.mark.usefixtures("history")
def test_a_rework_card_carries_the_history_as_context_only() -> None:
    card = _card(f"{rework_context.SOURCE_HOST}/two-sum/0a1b2c3d")
    text = for_source(_src(card), card)
    section = text.split(HEAD, 1)[1]
    assert "context only" in section.split("\n", 1)[0]
    assert "Wrong Answer python3" in section


@pytest.mark.usefixtures("history")
def test_any_other_card_gets_the_prompt_unchanged() -> None:
    card = _card("https://en.wikipedia.org/wiki/Hash_table")
    text = for_source(_src(card), card)
    assert text == system_prompt(card, [], None, [(card.id, card.front)])
    assert HEAD not in text


@pytest.mark.parametrize(
    "source",
    [
        "https://en.wikipedia.org/wiki/Hash_table",
        f"{rework_context.SOURCE_HOST}/",
        f"{rework_context.SOURCE_HOST}/../x/0a1b",
        "http://rework.leetcode-coach.invalid/two-sum/0a1b",
    ],
)
def test_only_a_rework_url_names_a_slug(source: str) -> None:
    assert rework_context.slug_of(source) is None


def test_a_rework_url_names_its_slug() -> None:
    url = f"{rework_context.SOURCE_HOST}/two-sum/0a1b2c3d"
    assert rework_context.slug_of(url) == "two-sum"
