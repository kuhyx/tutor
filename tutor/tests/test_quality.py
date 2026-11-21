# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The seven card rules' code checks, on the cards kuhy flagged."""

from __future__ import annotations

import pytest

from tutor.curriculum import quality


def _rules(
    front: str, back: str, mnemonic: str = "", *, hard: bool = False
) -> set[str]:
    return {p.rule for p in quality.problems(front, back, mnemonic, hard=hard)}


@pytest.mark.parametrize(
    "front",
    [
        "Czym jest serwer nazw (name server) i co przechowuje?",
        "Czym jest DMARC i na czym się opiera?",
        "Jakie są trzy polityki DMARC i co robi p=reject?",
        (
            "What happens to information outside the context window, and how can it "
            "still be supplied?"
        ),
        "What range does cosine similarity take, and what do +1, 0 and -1 mean?",
        "What three phases make up the S-curve, and which defines the startup?",
        "What is a vector? Why does it matter?",
    ],
)
def test_two_questions_in_one_card(front: str) -> None:
    assert quality.ONE_QUESTION in _rules(front, "An answer.")


@pytest.mark.parametrize(
    "front",
    [
        "What does a name server store?",
        "Co przechowuje serwer nazw?",
        "Which record maps a name to an IPv4 address and nothing else?",
    ],
)
def test_one_question_passes(front: str) -> None:
    assert _rules(front, "An answer.") == set()


@pytest.mark.parametrize(
    ("front", "back"),
    [
        ("Jak hosting WWW zwykle udostępnia harmonogram zadań?", "Przez panel."),
        ("How is cron offered?", "Usually through the hosting panel."),
        ("How is cron offered?", "In most cases through a panel."),
    ],
)
def test_hedged_card(front: str, back: str) -> None:
    assert quality.HEDGED in _rules(front, back)


def test_abbreviation_card_needs_a_mnemonic() -> None:
    front, back = "What does DKIM stand for?", "DomainKeys Identified Mail."
    assert _rules(front, back) == {quality.ABBREVIATION}
    assert _rules(front, back, "Domain Keys Identify Mail: DKIM signs it.") == set()
    assert quality.ABBREVIATION in _rules("Co oznacza skrót DKIM?", back)


def test_a_formula_card_answers_with_a_formula() -> None:
    front = "How do you calculate the length of a vector?"
    assert _rules(front, "Take the dot product with itself, then the root.") == {
        quality.FORMULA
    }
    assert _rules(front, "|v| = √(v·v)") == set()
    assert _rules("Jaki jest wzór na długość wektora?", "|v| = sqrt(v·v)") == set()


def test_a_hard_card_needs_a_mnemonic() -> None:
    front, back = "Where is the DKIM public key?", "In a TXT record in DNS."
    assert _rules(front, back, hard=True) == {quality.MNEMONIC}
    assert _rules(front, back, "TXT = the text of the key", hard=True) == set()


def test_how_often_and_computers_are_not_flagged() -> None:
    assert _rules("How often does a coil write its variable?", "Every scan.") == set()
    assert _rules("Jak często działa cron?", "Co minutę.") == set()
    assert _rules("Why is a desktop computer no PLC?", "It is not rugged.") == set()


def test_counts_and_text() -> None:
    found = quality.problems("A? B?", "Usually so.", "")
    assert quality.counts([found, []]) == {
        **dict.fromkeys(quality.RULE_IDS, 0),
        quality.ONE_QUESTION: 1,
        quality.HEDGED: 1,
    }
    assert all(rule in quality.RULES for rule in quality.RULE_IDS)
    assert quality.describe(found).startswith("one_question:")
