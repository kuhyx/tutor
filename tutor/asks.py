# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One thing per question box: an entry with two questions becomes two.

Each ``questions`` entry gets its own box and answer field, so two questions
in one entry make the learner answer both in one field. The rules forbid it
(rule 10) and the model did it anyway (2026-10-17), so :func:`split` cuts
such an entry after each prose ``?`` that ends a sentence. Lead-in text stays
with the first question, a trailing task with the last; the parts get no
choices, which were written for the whole entry. The check is never split.
"""

from __future__ import annotations

from itertools import pairwise
import re
from typing import TYPE_CHECKING, Final

from tutor import codespans

if TYPE_CHECKING:
    from collections.abc import Sequence

# A question mark that ends a sentence: whitespace follows it.
_END: Final = re.compile(r"\?\s+")


def entry(text: str) -> list[str]:
    """``text`` as one question per part; ``[text]`` when it asks one thing."""
    said = text.strip()
    cuts: list[int] = []
    at = 0
    for chunk, code in codespans.pieces(said):
        if not code:
            cuts += [at + found.end() for found in _END.finditer(chunk)]
        at += len(chunk)
    if cuts and not said.endswith("?"):
        cuts.pop()  # a trailing task stays with the last question
    if not cuts:
        return [text]
    bounds = [0, *cuts, len(said)]
    return [said[a:b].strip() for a, b in pairwise(bounds)]


def split(questions: Sequence[str], raw: object) -> tuple[list[str], list[object]]:
    """The questions one per entry, with the raw choices still lined up.

    An unsplit entry keeps its own raw choices; each split part gets ``None``
    (no choices). ``raw`` that is not a list counts as no choices at all.
    """
    listed = list(raw) if isinstance(raw, (list, tuple)) else []
    said: list[str] = []
    aligned: list[object] = []
    for i, question in enumerate(questions):
        parts = entry(question)
        said += parts
        own = listed[i] if i < len(listed) else None
        aligned += [own] if len(parts) == 1 else [None] * len(parts)
    return said, aligned
