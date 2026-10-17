# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``card_edits`` in a turn: optional, read forgivingly, in the schema."""

from __future__ import annotations

from tutor.card_requests import CardEdit, parse
from tutor.models import REQUIRED_FIELDS, TURN_SCHEMA, TutorTurn
from tutor.tests.test_models import raw_turn


def test_card_edits_are_optional_but_in_the_schema() -> None:
    assert "card_edits" not in REQUIRED_FIELDS
    required = TURN_SCHEMA["required"]
    assert isinstance(required, list)
    assert "card_edits" in required
    assert TutorTurn.from_json(raw_turn()).card_edits == ()


def test_card_edits_parse_and_drop_junk() -> None:
    raw = raw_turn(
        card_edits=[
            {"op": "remove", "card": " c1 ", "reason": "wrong"},
            {"op": "edit", "front": "New?", "back": ""},
            {"op": "add", "topic": "a", "front": "F?", "back": "B.", "source": "u"},
            {"op": "explode"},
            "remove",
        ]
    )
    edits = TutorTurn.from_json(raw).card_edits
    assert edits == (
        CardEdit("remove", card="c1", reason="wrong"),
        CardEdit("edit", front="New?"),
        CardEdit("add", topic="a", front="F?", back="B.", source="u"),
    )


def test_parse_reads_only_lists() -> None:
    assert parse(None) == ()
    assert parse({"op": "remove"}) == ()
    assert parse([{"op": "remove", "card": 3}]) == (CardEdit("remove", card="3"),)
