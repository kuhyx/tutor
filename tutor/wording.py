# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Phrases the learner never reads, cut from every model turn by code.

"In your own words" asks for an original phrasing when only a correct answer
counts (any wording passes, verbatim included). The rules forbid it, and the
model wrote it anyway on the first live turn after they did (2026-10-17), so
:func:`scrub` takes it out of the message, the questions and the check.
"""

from __future__ import annotations

import re
from typing import Final

_OWN_WORDS: Final = re.compile(
    r"(?P<pre>\s*,?\s*)\b(?P<lead>in|using|with)\s+(?:your|their)\s+own[\s-]+words\b"
    r",?(?P<gap>\s*)(?P<next>\w?)",
    re.IGNORECASE,
)


def _cut(found: re.Match[str]) -> str:
    """The text that replaces one match: a sentence start stays capitalised."""
    if found["lead"][0].isupper():
        return found["pre"].replace(",", "") + found["next"].upper()
    return found["gap"] + found["next"]


def scrub(text: str) -> str:
    """``text`` without "in your own words" (and its "using"/"their" forms)."""
    return _OWN_WORDS.sub(_cut, text)
