# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The deterministic relevance layer: terms, title fit, ranking, the query."""

from __future__ import annotations

from tutor.curriculum import relevance
from tutor.curriculum.records import Meta, Module
from tutor.curriculum.wiki import WIKIBOOKS, WIKIPEDIA, Page

MODULE = Module(
    "car-overview",
    "Car",
    "The main systems of a car and how they work together: engine, "
    "transmission, wheels.",
)
META = Meta("How a car works", "I want to learn how a car works", "active", 0)


def test_terms_drop_filler_and_stem() -> None:
    assert relevance.terms("How the Cars' engines WORK, a gas") == {
        "car",
        "engine",
        "gas",
    }
    assert relevance.terms("transmission") == {"transm"}


def test_title_fit() -> None:
    wanted = relevance.focus(META, MODULE)
    assert relevance.title_fit("Car", wanted) == 1.0
    assert relevance.title_fit("The Cars", wanted) == 1.0
    assert relevance.title_fit("How To Build a Pinewood Derby Car/Rules", wanted) == 0.2
    assert relevance.title_fit("Central African Republic", wanted) == 0.0
    assert relevance.title_fit("Muscle car", wanted) == 0.5
    assert relevance.title_fit("The", wanted) == 0.0


def test_coverage() -> None:
    wanted = {"engine", "wheel"}
    assert relevance.coverage("an engine turns", wanted) == 0.5
    assert relevance.coverage("anything", set()) == 0.0


def test_shortlist_keeps_exact_hits_first_and_ranks_search_hits() -> None:
    wanted = relevance.focus(META, MODULE)
    pages = [
        Page(WIKIPEDIA, "Car engine", "engine only", exact=False),
        Page(WIKIPEDIA, "Car", "x", exact=True),
        Page(WIKIBOOKS, "Pinewood Derby Car", "car wheels engine", exact=False),
        Page(WIKIPEDIA, "Car transmission", "engine wheels transmission", exact=False),
        Page(WIKIPEDIA, "Suspension", "unrelated", exact=True),
    ]
    assert [p.title for p in relevance.shortlist(pages, wanted)] == [
        "Car",
        "Suspension",
        "Car transmission",
        "Car engine",
    ]


def test_query_adds_new_summary_words() -> None:
    assert relevance.query(MODULE) == "Car systems engine transmission"
    assert relevance.query(Module("m", "Car engine", "The engine.")) == "Car engine"
