# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The check is one typed question: no tap choices, no "in your own words".

2026-10-17: a check worded "explain X in your own words" came with three tap
targets, and a right tap was followed by the same question again, typed. The
learner wants exactly one final question, answered by typing, graded on
being correct (the wording is theirs to pick, verbatim is fine).
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from tutor import choices, models, prompt, scripted, wording
from tutor.curriculum import profiles
from tutor.prompt_rules import render_system

OWN_WORDS = ("own words", "own-words")


def _free_of_own_words(text: str) -> bool:
    return not any(phrase in text.lower() for phrase in OWN_WORDS)


@pytest.mark.parametrize(
    "profile",
    [profiles.automation(), profiles.generated("car", {"domain": "cars"})],
    ids=["automation", "generated"],
)
def test_rules_never_say_own_words(profile: profiles.Profile) -> None:
    text = render_system(profile).lower()
    # Named exactly once: as the phrase the tutor must never write.
    ban = 'never write "in your own words"'
    assert ban in text
    assert _free_of_own_words(text.replace(ban, ""))


def test_schema_docs_note_and_persona_never_say_own_words() -> None:
    lines = prompt._check_line(due=True, check_open=False, attempt=0)
    for text in (models._CHOICES_DOC, scripted._PERSONA, *lines):
        assert _free_of_own_words(text)


def test_check_schema_has_no_choices() -> None:
    props = cast("dict[str, Any]", models.TURN_SCHEMA["properties"])
    check = props["check"]["anyOf"][0]
    assert "choices" not in check["properties"]
    assert "choices" not in check["required"]


def test_repair_check_drops_any_choices_the_model_sent() -> None:
    raw = {"question": "What is a PLC?", "concept": "plc", "choices": ["a", "b", "c"]}
    assert choices.repair_check(raw) == {**raw, "choices": []}


# 2026-10-17, live session 20261017-184924-ec1b turn 9: the model wrote it
# into an ordinary question under the new rules, so code takes it out.
LIVE = (
    "Imagine a record `bar.example.com.  CNAME  foo.example.com.` Explain in your "
    "own words what it tells the DNS server, and why bar and foo sit on those sides."
)


@pytest.mark.parametrize(
    ("said", "kept"),
    [
        (
            LIVE,
            (
                "Imagine a record `bar.example.com.  CNAME  foo.example.com.` Explain "
                "what it tells the DNS server, and why bar and foo sit on those sides."
            ),
        ),
        ("In your own words, what is a PLC?", "What is a PLC?"),
        ("What is a PLC, in your own words?", "What is a PLC?"),
        ("Say it in your OWN words.", "Say it."),
        ("Restate it using your own words: why?", "Restate it: why?"),
        ("Nothing to change here.", "Nothing to change here."),
    ],
)
def test_own_words_is_cut_from_what_the_learner_reads(said: str, kept: str) -> None:
    assert wording.scrub(said) == kept


def test_a_model_turn_reaches_the_learner_without_own_words() -> None:
    raw = {
        "message": "Right. Now in your own words, one more.",
        "low_effort": False,
        "questions": [LIVE],
        "choices": [[]],
        "check": {"question": "In your own words, what is a CNAME?", "concept": "c"},
        "check_result": None,
        "images": [],
        "diagram": None,
        "concepts_mastered": [],
        "card_done": False,
    }
    got = models.TutorTurn.from_json(raw)
    seen = " ".join([got.message, *got.questions, str(got.check)])
    assert _free_of_own_words(seen)
    assert got.check == {"question": "What is a CNAME?", "concept": "c", "choices": []}


def test_a_check_without_a_question_is_left_for_the_model_repair() -> None:
    assert choices.repair_check({"concept": "c"}) == {"concept": "c", "choices": []}
