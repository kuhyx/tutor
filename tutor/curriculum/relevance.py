# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Deterministic relevance: which candidate pages can serve a module.

The model picks sources and judges cards (``judge``), but a code layer runs
first so a loosely matching search hit never even reaches it: a search hit
whose title is mostly words the module never mentions ("How To Build a
Pinewood Derby Car/Rules" for "Car") is dropped, and the rest are ranked by
how much of the module's wording their text covers. Exact-title hits (the
canonical article the plan or the model named) are kept and come first.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from tutor.curriculum.records import Meta, Module
    from tutor.curriculum.wiki import Page

# A search hit's title must be mostly module words: both of two, 2 of 3.
MIN_TITLE_FIT: Final = 0.6
# Ranking looks at the start of the text, about what the model is shown.
_RANK_WORDS: Final = 2500
_STEM: Final = 6
_PLURAL: Final = 4  # "gas" stays "gas", "cars" becomes "car"
_FILLER: Final = """a about also an and are as at basic be between by can do does each
for from has have how i idea in into is it its learn like main many more most of on
or other our plus some such than that the their them then these they this those to
together understand use used very want what when where which why with work works"""
_STOP: Final = frozenset(_FILLER.split())


def terms(text: str) -> set[str]:
    """Content words, lowercased, crudely stemmed (plural ``s``, 6 letters)."""
    out = set()
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in _STOP:
            continue
        stem = word[:-1] if len(word) >= _PLURAL and word.endswith("s") else word
        out.add(stem[:_STEM])
    return out


def focus(meta: Meta, module: Module) -> set[str]:
    """What the module is about: its title and summary, the subject's goal."""
    return terms(f"{module.title} {module.summary} {meta.title} {meta.goal}")


def title_fit(title: str, wanted: set[str]) -> float:
    """Share of the title's words that the module uses (0 for no words)."""
    words = terms(title)
    return len(words & wanted) / len(words) if words else 0.0


def coverage(text: str, wanted: set[str]) -> float:
    """Share of the module's words found in the start of ``text``."""
    seen = terms(" ".join(text.split()[:_RANK_WORDS]))
    return len(wanted & seen) / len(wanted) if wanted else 0.0


def shortlist(pages: list[Page], wanted: set[str]) -> list[Page]:
    """Exact-title hits in order, then fitting search hits by coverage."""
    exact = [p for p in pages if p.exact]
    hits = [
        p for p in pages if not p.exact and title_fit(p.title, wanted) >= MIN_TITLE_FIT
    ]
    hits.sort(key=lambda p: -coverage(p.text, wanted))
    return exact + hits


def query(module: Module, extra: int = 3) -> str:
    """A search query: the module title plus its summary's first new words."""
    have = terms(module.title)
    added: list[str] = []
    for word in re.findall(r"[A-Za-z0-9]+", module.summary):
        key = terms(word)
        if key and not key & have and len(added) < extra:
            added.append(word.lower())
            have |= key
    return " ".join([module.title, *added])
