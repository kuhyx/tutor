# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Word tokenizers keep Polish letters inside words (NFC, same set as ids)."""

from __future__ import annotations

import re
import unicodedata

import pytest

from tutor import commons, filler, sources
from tutor.cards import Card, Topic
from tutor.curriculum import relevance
from tutor.curriculum.ids import tokenize
from tutor.curriculum.records import Module
from tutor.distractors import _words as distractor_words

POLISH = "Pojęcia z łódzkiego maila: zażółć gęślą jaźń!"
WANT = ["pojęcia", "z", "łódzkiego", "maila", "zażółć", "gęślą", "jaźń"]


def _nfd(text: str) -> str:
    out = unicodedata.normalize("NFD", text)
    assert out != text
    return out


def test_words_keep_polish_letters_whole() -> None:
    assert tokenize(POLISH) == WANT
    assert tokenize(_nfd(POLISH)) == WANT


@pytest.mark.parametrize(
    "text", ["How a Car works?", "4-20 mA I/O", "Café au lait", "ÜBER x_y 12ab", ""]
)
def test_words_match_the_old_ascii_tokenizer_on_ascii(text: str) -> None:
    if text.isascii():
        assert tokenize(text) == re.findall(r"[a-z0-9]+", text.lower())


def test_commons_tokens_keep_polish_words() -> None:
    assert commons.tokens("Pojęcia łódź") == {"pojęcia", "łódź"}
    assert commons.tokens(_nfd("Pojęcia łódź")) == {"pojęcia", "łódź"}


def test_distractor_words_keep_polish_words() -> None:
    card = Card(
        "c", "Czym są pojęcia?", "Pojęcia i łódź", "u", "x", Topic("t", "t", ("",))
    )
    assert distractor_words(card) == {"czym", "pojęcia", "łódź"}
    nfd = Card(
        "c", _nfd("Czym są pojęcia?"), _nfd("Pojęcia i łódź"), "u", "x", card.topic
    )
    assert distractor_words(nfd) == {"czym", "pojęcia", "łódź"}


def test_relevance_terms_and_query_keep_polish_words() -> None:
    assert relevance.terms("Pojęcia łódź") == {"pojęci", "łódź"}
    assert relevance.terms(_nfd("Pojęcia łódź")) == {"pojęci", "łódź"}
    mod = Module("m", "Maile", "Pojęcia łódź skrzynka", [])
    assert relevance.query(mod) == "Maile pojęcia łódź skrzynka"


def test_excerpt_check_ignores_nfc_vs_nfd() -> None:
    page = _nfd("Zażółć gęślą jaźń to  pangram.")
    excerpt = "zażółć gęślą jaźń to pangram."
    assert sources.normalise(page) == sources.normalise(excerpt)
    assert sources.normalise(excerpt) in sources.normalise(page)
    assert sources.normalise("ŁÓDŹ") == "łódź"


def test_filler_normalise_composes_first() -> None:
    assert filler.normalise(_nfd("Łódź!")) == filler.normalise("Łódź!") == "łódź"
