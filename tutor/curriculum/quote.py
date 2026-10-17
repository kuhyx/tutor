# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pick the verbatim sentence of a page that supports a card's answer.

The tutor proposes a new card without an excerpt (it has no tools, so any
quote it wrote would be from memory). Code quotes one instead: the page's
sentence (or a 6-40 word window of a long one) sharing the most content
words with the answer, if it shares enough of them. The card then still goes
through the unchanged excerpt check (``card_rules.source_problem``).
"""

from __future__ import annotations

import math
import re
from typing import Final

from tutor import sources

MIN_WORDS: Final = 6
MAX_WORDS: Final = 40
# An excerpt must share this many of the answer's content words (and at
# least a third of them), or nothing on the page is taken to support it.
MIN_SHARED: Final = 3
_MIN_LEN: Final = 3  # shorter words never count
_SENTENCE: Final = re.compile(r"(?<=[.!?])\s+")
_FOOTNOTE: Final = re.compile(r"\[\s*(?:\d+|[a-z]|citation needed|note \d+)\s*\]")
_WORD: Final = re.compile(r"[a-z0-9]+")
_STOP: Final = frozenset(
    [
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "any",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "its",
        "with",
        "that",
        "this",
        "from",
        "they",
        "will",
        "would",
        "there",
        "their",
        "what",
        "when",
        "which",
        "into",
        "than",
        "then",
        "them",
        "these",
        "those",
        "been",
        "have",
        "were",
        "does",
        "also",
        "such",
    ]
)


def content_words(text: str) -> set[str]:
    """Lowercase words of three or more letters that carry meaning."""
    found = _WORD.findall(sources.normalise(text))
    return {w for w in found if len(w) >= _MIN_LEN and w not in _STOP}


def _windows(sentence: str) -> list[str]:
    """The sentence, or 40-word windows of it (10 words apart) when longer."""
    words = sentence.split()
    if len(words) <= MAX_WORDS:
        return [sentence] if len(words) >= MIN_WORDS else []
    last = len(words) - MAX_WORDS
    starts = [*range(0, last, 10), last]
    return [" ".join(words[i : i + MAX_WORDS]) for i in starts]


def supporting(text: str, back: str, front: str = "", hint: str = "") -> str | None:
    """The best supporting excerpt of ``text`` for the answer ``back``, or None.

    Scored by the answer's content words it contains (ties: the front's, then
    the earlier one); footnote markers are dropped. ``hint``, the words the
    tutor expects in the sentence (in the page's language: a card in another
    language shares no word with it), replaces the answer's words.
    """
    answer = content_words(hint) or content_words(back)
    question = content_words(f"{front} {back}")
    need = max(MIN_SHARED, math.ceil(len(answer) / 3))
    best: tuple[int, int] = (0, 0)
    chosen = None
    flat = " ".join(_FOOTNOTE.sub("", text).split())
    for sentence in _SENTENCE.split(flat):
        for window in _windows(sentence):
            words = content_words(window)
            score = (len(words & answer), len(words & question))
            if score[0] >= need and score > best:
                best, chosen = score, window
    return chosen
