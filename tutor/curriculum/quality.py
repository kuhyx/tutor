# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The seven card rules kuhy's flags asked for, and the ones code can check.

Every rule comes from a card he flagged or feedback he filed (2026-10-15 to
2026-11-21). :data:`RULES` is the wording the drafting model, the judge
(``quality_judge``) and the repair call all read. :func:`problems` is the
mechanical part, run on every drafted and edited card: a second question
mark or an "and what / i co" joining two questions, a hedge word, an
abbreviation card without a memory aid, a "calculate" card whose answer
holds no formula, a card the learner found hard without a memory aid. What
needs judgement (an unguessable name or number, two terms in one card, a
matter of opinion) is the judge's.
"""

from __future__ import annotations

import re
from typing import Final, NamedTuple

ONE_QUESTION: Final = "one_question"
UNGUESSABLE: Final = "unguessable"
ABBREVIATION: Final = "abbreviation"
ONE_TERM: Final = "one_term"
FORMULA: Final = "formula"
HEDGED: Final = "hedged"
MNEMONIC: Final = "mnemonic"
RULE_IDS: Final = (
    ONE_QUESTION,
    UNGUESSABLE,
    ABBREVIATION,
    ONE_TERM,
    FORMULA,
    HEDGED,
    MNEMONIC,
)
RULES: Final = f"""\
The card rules (the learner flagged cards that broke each one):
- `{ONE_QUESTION}`: a card asks exactly ONE question with ONE answer. Never \
"what is X and what does it do", "which three ... and which one ...", or a \
range plus the meaning of its ends: those are two cards.
- `{UNGUESSABLE}`: a card never asks for an arbitrary name or number the \
learner cannot reason out (a magic record name, a port or version number, a \
year, a limit). Ask what the thing does or why it exists and state the name \
or number in the question, or leave the fact out.
- `{ABBREVIATION}`: a card about what an abbreviation stands for asks ONLY \
for the expansion (the answer is the expanded words and nothing about how \
the thing works) and carries a `mnemonic` that makes the expansion easy to \
recall.
- `{ONE_TERM}`: one abbreviation or term per card. Two terms (fine-tuning \
and RLHF) are two cards, and an abbreviation used in an answer is written \
out in full the first time.
- `{FORMULA}`: a card on how something is calculated asks "how do you \
calculate X" and its answer is the mathematical formula itself, not a \
description of the steps in words.
- `{HEDGED}`: no subjective or hedged card. A card states a definite, \
checkable fact; no "usually", "typically", "often", "zwykle", "zazwyczaj", \
no "best" or "works best" opinions. A fact the source only hedges is not \
a card.
- `{MNEMONIC}`: a card marked hard for the learner carries a `mnemonic`: a \
short vivid memory aid (one line, at most 40 words) for exactly its answer.
"""
# "..., and how ...?" / "... i co ...?": a second question joined to the first.
_ASKS: Final = (
    r"what|how|why|which|where|when|who|whom|whose|"
    r"co|jak|jaki\w*|dlaczego|czym|czemu|czego|gdzie|kiedy|kto|kogo|"
    r"któr\w+|ile|po co"
)
_PREPOSITIONS: Final = r"na|w|we|do|z|ze|po|od|dla|o|przy|in|on|at|by|for|to|with"
_SECOND: Final = re.compile(
    rf"\b(?:and|i|oraz|a)\s+(?:(?:{_PREPOSITIONS})\s+)?(?:{_ASKS})\b", re.IGNORECASE
)
_HEDGES: Final = re.compile(
    r"\b(?:usually|typically|generally|(?<!how )often|sometimes|commonly|probably|"
    r"in most cases|tends? to|zwykle|zazwyczaj|najczęściej|przeważnie|"
    r"(?<!jak )często|"
    r"czasem|czasami|raczej|prawdopodobnie|w większości)\b",
    re.IGNORECASE,
)
_EXPANSION: Final = re.compile(
    r"stands? for|abbreviat|acronym|skrót|skrot|rozwini|rozwija", re.IGNORECASE
)
_CALCULATE: Final = re.compile(
    r"\b(?:formula|calculate[sd]?|calculating|calculations?|compute[sd]?"
    r"|wz[oó]r\w*|oblicz\w*|wylicz\w*)\b",
    re.IGNORECASE,
)
# = and the maths signs: root, sums, dot, times, powers, fraction slash,
# division, <=, >=, about-equal (escaped: ruff reads them as look-alikes).
_MATHS: Final = re.compile(
    r"[=^\u221a\u2211\u03a3\u00b7\u00d7\u00b2\u00b3\u2044\u00f7\u2264\u2265\u2248]"
    r"|\bsqrt\b|\\frac"
)


class Problem(NamedTuple):
    """One rule a card breaks, and what code saw."""

    rule: str
    why: str


def problems(
    front: str, back: str, mnemonic: str = "", *, hard: bool = False
) -> list[Problem]:
    """The rules code can see ``front`` / ``back`` / ``mnemonic`` break.

    ``hard``: the learner flagged the card hard or failed it in review.
    """
    found: list[Problem] = []
    if front.count("?") > 1:
        found.append(Problem(ONE_QUESTION, "the front has two question marks"))
    elif joined := _SECOND.search(front):
        why = f'the front joins a second question with "{joined.group()}"'
        found.append(Problem(ONE_QUESTION, why))
    if hedge := _HEDGES.search(f"{front} {back}"):
        found.append(Problem(HEDGED, f'hedge word "{hedge.group()}"'))
    aid = bool(mnemonic.strip())
    if _EXPANSION.search(front) and not aid:
        found.append(Problem(ABBREVIATION, "an expansion card needs a mnemonic"))
    elif hard and not aid:
        found.append(Problem(MNEMONIC, "hard for the learner: needs a mnemonic"))
    if _CALCULATE.search(front) and not _MATHS.search(back):
        found.append(Problem(FORMULA, "the answer holds no formula"))
    return found


def describe(found: list[Problem]) -> str:
    """``rule: why; rule: why`` for a refusal or a repair prompt."""
    return "; ".join(f"{p.rule}: {p.why}" for p in found)


def counts(found: list[list[Problem]]) -> dict[str, int]:
    """Cards breaking each rule (every rule listed, 0 when none)."""
    out = dict.fromkeys(RULE_IDS, 0)
    for card in found:
        for rule in {p.rule for p in card}:
            out[rule] = out.get(rule, 0) + 1  # also ``no_verdict``
    return out
