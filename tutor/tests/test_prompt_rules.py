# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Rule wording pinned by live failures, rendered for every kind of profile.

2026-10-17: the tutor wrote "Masz już opanowane m.in. DNS, rekord A i CNAME"
and then asked what CNAME does, four cards in a row. Rule 1 asked about
every key term and rule 8 allowed a recall question per mastered concept.
"""

from __future__ import annotations

import re

import pytest

from tutor.cards import Card, Topic
from tutor.curriculum import profiles
from tutor.prompt import system_prompt

CARD = Card(
    id="dns-cname-chain",
    front="What does a CNAME pointing at another CNAME do?",
    back="The resolver follows the chain to the final A record.",
    source="https://example.org/dns",
    excerpt="the resolver follows the chain",
    topic=Topic(stem="dns", title="DNS", prefixes=("dns",)),
)
HEADING = "Already mastered concepts"
PROFILES = pytest.mark.parametrize(
    "profile",
    [profiles.automation(), profiles.generated("car", {"domain": "cars"})],
    ids=["automation", "generated"],
)


def _rule(text: str, number: int) -> str:
    """Rule ``number`` of the rendered prompt, on one line."""
    found = re.search(
        rf"^{number}\. (.*?)(?=^\d+\. |^# )", text, re.MULTILINE | re.DOTALL
    )
    assert found is not None
    return " ".join(found[1].split())


@PROFILES
def test_diagnosis_skips_mastered_terms(profile: profiles.Profile) -> None:
    text = system_prompt(CARD, ["dns", "cname"], profile)
    assert f"# {HEADING}\ndns, cname\n" in text  # the list the rules name
    rule = _rule(text, 1)
    assert f'NOT listed under "{HEADING}"' in rule
    assert "every key term is already mastered" in rule
    assert "new relation the card adds" in rule


@PROFILES
def test_resume_never_re_asks_a_mastered_concept(profile: profiles.Profile) -> None:
    rule = _rule(system_prompt(CARD, ["cname"], profile), 8)
    assert f'"{HEADING}"' in rule
    assert "never re-ask what a mastered concept is or does" in rule
    assert "build on it" in rule
    assert "only if the target needs it" not in rule


@PROFILES
def test_style_counts_only_unmastered_terms(profile: profiles.Profile) -> None:
    assert "one per unmastered term" in _rule(system_prompt(CARD, [], profile), 10)


# 2026-10-17: one box asked two things at once ("how does X differ from Y?
# what happens when Y changes?"), so one answer field had to carry both.
@PROFILES
def test_style_asks_one_thing_per_question(profile: profiles.Profile) -> None:
    rule = _rule(system_prompt(CARD, [], profile), 10)
    assert "Each `questions` entry asks exactly ONE thing" in rule
    assert "never two questions in one entry" in rule
    assert '"X and Y"' in rule


# 2026-10-17: the tutor may fix the deck itself (kuhy): on the learner's
# criticism and on its own initiative, applied at once with a chat notice.
@PROFILES
def test_card_edits_rule(profile: profiles.Profile) -> None:
    text = system_prompt(CARD, [], profile)
    rule = _rule(text, 15)
    assert "`card_edits`" in rule
    for op in ('"edit"', '"add"', '"remove"'):
        assert op in rule
    assert "on your own initiative" in rule
    assert '`card` is an id from "Cards of this topic"' in rule
    assert "the app quotes" in rule
    assert "`quote`: the words you expect in that sentence" in rule
    assert "next engine note" in rule
    assert "ends this session" in rule
    assert "from the card's next session" in rule
    assert "`card_edits` (usually [], rule 15)" in text.split("# Output", 1)[1]


# 2026-10-17 sandbox: after removing the card the tutor said "the next card
# opens in a moment" while none was left. The app shows what comes next.
@PROFILES
def test_card_removal_promises_nothing(profile: profiles.Profile) -> None:
    rule = _rule(system_prompt(CARD, [], profile), 15)
    assert "confirm the removal only" in rule
    assert "never promise what comes next" in rule
    assert "and opens the next card" not in rule


# 2026-10-17 sandbox, real model: one "?" but two asks: "na co CNAME może
# wskazywać..., a na co nie może? Jeśli masz przypuszczenie, napisz też,
# dlaczego" and "...a czego nie można? Uzasadnij."
@PROFILES
def test_style_bans_compound_and_tacked_on_why(profile: profiles.Profile) -> None:
    rule = _rule(system_prompt(CARD, [], profile), 10)
    assert '"X, a Y?"' in rule
    assert "no tacked-on" in rule
    for tail in ('"and why?"', '"uzasadnij"', '"dlaczego"', '"explain why"'):
        assert tail in rule
    assert "in a LATER turn" in rule
    assert "Bad:" in rule
    assert "Good:" in rule
