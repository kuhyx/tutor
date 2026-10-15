# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Answer choices: one entry per question, either none or exactly three.

The model offers three short answers (one right, two plausible wrong) under a
question with one right answer, and none under an open one. Its output is
repaired, never trusted: an entry that is not three distinct short strings
becomes ``[]``, and the list is padded or cut to line up with the questions.
Turns logged before choices existed read as all ``[]``.
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tutor.models import TutorTurn

PER_QUESTION: Final = 3
# The prompt asks for at most 12 words; past this a choice is no tap target.
MAX_WORDS: Final = 20
_RANDOM: Final = secrets.SystemRandom()

Choice = tuple[str, ...]


def entry(raw: object) -> Choice:
    """One question's choices, or ``()`` when they are not three short strings."""
    if not isinstance(raw, (list, tuple)) or len(raw) != PER_QUESTION:
        return ()
    if not all(isinstance(item, str) for item in raw):
        return ()
    kept = tuple(str(item).strip() for item in raw)
    if not all(kept) or len({k.casefold() for k in kept}) != PER_QUESTION:
        return ()
    if any(len(k.split()) > MAX_WORDS for k in kept):
        return ()
    return kept


def mixed(choice: Choice) -> Choice:
    """``choice`` in a random order: the model tends to put the right one first."""
    shuffled = list(choice)
    _RANDOM.shuffle(shuffled)
    return tuple(shuffled)


def _at(raw: object, index: int) -> object:
    return raw[index] if isinstance(raw, (list, tuple)) and index < len(raw) else None


def pair(
    questions: Sequence[object], raw: object
) -> tuple[tuple[str, ...], tuple[Choice, ...]]:
    """A model turn's questions and choices, repaired and mixed, still aligned.

    Blank questions are dropped together with their choices, so a gap in the
    questions never shifts the choices onto the wrong question.
    """
    pairs = [(str(q).strip(), entry(_at(raw, i))) for i, q in enumerate(questions)]
    kept = [(q, mixed(c)) for q, c in pairs if q]
    return tuple(q for q, _ in kept), tuple(c for _, c in kept)


def aligned(questions: Sequence[object], raw: object) -> list[list[str]]:
    """One ``[]``-or-three list per question (old turns: all ``[]``); no mixing."""
    return [list(entry(_at(raw, i))) for i in range(len(questions))]


def boxes(
    questions: Sequence[str], raw: object, check: object
) -> tuple[list[str], list[list[str]]]:
    """The page's question boxes and their choices, without a copy of the check."""
    pairs = zip(questions, aligned(questions, raw), strict=True)
    kept = [(q, c) for q, c in pairs if q != check]
    return [q for q, _ in kept], [c for _, c in kept]


def reworded(checked: TutorTurn, draft: TutorTurn) -> tuple[Choice, ...]:
    """The choices for questions a picture check reworded (``media``).

    The check reply's own; if it dropped them all, the draft's, as long as the
    questions still line up one for one.
    """
    same = len(checked.questions) == len(draft.questions)
    return draft.choices if same and not any(checked.choices) else checked.choices
