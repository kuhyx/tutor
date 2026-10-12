# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The model's relevance calls: titles, source pick, the per-card gate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.curriculum import judge, plan_context
from tutor.curriculum.plan_context import Scope
from tutor.curriculum.records import Meta, Module, Plan
from tutor.curriculum.wiki import WIKIPEDIA, Page
from tutor.tests._cur import card, make_ctx

if TYPE_CHECKING:
    from pathlib import Path

META = Meta("How a car works", "I want to learn how a car works", "active", 0)
MODULE = Module("car-overview", "Car", "The main systems of a car.")
ENGINE = Module("engine", "Engine", "Pistons and the crankshaft.")
BASICS = Module("basics", "Energy", "Energy and force.")
PLAN = Plan(1, "approved", "", [BASICS, MODULE, ENGINE])
SCOPE = Scope(META, MODULE, PLAN)
PAGES = [Page(WIKIPEDIA, f"P{i}", "word " * 300, exact=True) for i in range(1, 5)]


def test_propose_titles(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies += [
        {"titles": [" Car ", "", 3, "Engine", "A", "B", "C", "D"]},
        {"titles": "Car"},
    ]
    assert judge.propose_titles(ctx, SCOPE) == ["Car", "Engine", "A", "B", "C"]
    assert judge.propose_titles(ctx, SCOPE) == []
    system, prompt = fakes.prompts[0]
    assert system == judge.TITLES_SYSTEM
    assert "Learner's goal: I want to learn how a car works" in prompt
    assert '- basics "Energy": Energy and force.' in prompt.split("Later")[0]
    assert '- engine "Engine": Pistons and the crankshaft.' in prompt


def test_pick_sources(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    assert judge.pick_sources(ctx, SCOPE, [], 3) == []
    assert not fakes.prompts  # no candidates: no model call
    fakes.replies += [
        {"keep": [3, True, 0, 9, 3, "1", 1, 2, 4], "why": ""},
        {"keep": None, "why": ""},
    ]
    picked = judge.pick_sources(ctx, SCOPE, PAGES, 3)
    assert [p.title for p in picked] == ["P3", "P1", "P2"]
    assert judge.pick_sources(ctx, SCOPE, PAGES, 3) == []
    prompt = fakes.prompts[0][1]
    assert (
        '<candidate n="2" title="P2" url="https://en.wikipedia.org/wiki/P2">' in prompt
    )
    first = prompt.split('<candidate n="1"', 1)[1].split("</candidate>")[0]
    assert len(first.split()) < judge.LEAD_WORDS + 10


def test_gate_fails_closed(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    assert judge.gate(ctx, SCOPE, {}, {}, {}) == ({}, [])
    drafted = {"a": card("m", 1), "b": card("m", 2), "c": card("m", 3)}
    fakes.replies.append(
        {
            "verdicts": [
                {"id": "a", "on_topic": True, "module": MODULE.id, "reason": "parts"},
                {"id": "b", "on_topic": False, "module": MODULE.id, "reason": "toy"},
                {"id": 7, "on_topic": True},
                "junk",
            ]
        }
    )
    titles = {"https://en.wikipedia.org/wiki/Thing": "Thing"}
    kept, problems = judge.gate(ctx, SCOPE, drafted, titles, {})
    assert list(kept) == ["a"]
    assert problems == ["b: off topic (toy)", "c: off topic (no verdict)"]
    assert '"source": "Thing"' in fakes.prompts[0][1]
    fakes.replies.append({"verdicts": {}})
    assert judge.gate(ctx, SCOPE, {"a": card("m", 1)}, {}, {})[0] == {}


def test_gate_keeps_only_cards_best_placed_here(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    drafted = {k: card("m", i) for i, k in enumerate("abcdef")}
    fakes.replies.append(
        {
            "verdicts": [
                {"id": "a", "on_topic": True, "module": MODULE.id, "reason": "ok"},
                {"id": "b", "on_topic": True, "module": "engine", "reason": "pistons"},
                {"id": "c", "on_topic": True, "module": "basics", "reason": "energy"},
                {"id": "d", "on_topic": True, "module": "nope", "reason": "?"},
                {"id": "e", "on_topic": True, "reason": "no module"},
                {"id": "f", "on_topic": False, "module": "engine", "reason": "crank"},
            ]
        }
    )
    kept, problems = judge.gate(ctx, SCOPE, drafted, {}, {})
    assert list(kept) == ["a"]
    assert problems == [
        "b: belongs to later module engine (pistons)",
        "c: duplicates earlier module basics (energy)",
        "d: no module named (?)",
        "e: no module named (no module)",
        "f: belongs to later module engine (crank)",
    ]
    system, prompt = fakes.prompts[0]
    assert "fits it best" in system
    assert "Module (car-overview): Car" in prompt


def test_gate_schema_names_every_module_this_one_first(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    schemas: list[dict[str, Any]] = []

    def model(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        schemas.append(schema)
        return fakes.model(system, prompt, schema)

    ctx.model = model
    fakes.replies.append({"verdicts": []})
    judge.gate(ctx, SCOPE, {"a": card("m", 1)}, {}, {"k": card("m", 2)})
    verdict = schemas[0]["properties"]["verdicts"]["items"]
    assert verdict["required"] == ["id", "on_topic", "module", "repeats", "reason"]
    assert verdict["properties"]["repeats"]["enum"] == ["", "k", "a"]
    assert (
        'Already in the deck (id: front): {"k": "What is thing 2 of m?"}'
        in (fakes.prompts[0][1])
    )
    assert verdict["properties"]["module"]["enum"] == [
        "car-overview",
        "basics",
        "engine",
    ]
    alone = Scope(META, MODULE, None)
    assert "Earlier modules (already taught" in alone.about()
    assert alone.about().count("(none)") == 2
    assert plan_context.module_ids(None, MODULE) == ["car-overview"]


def test_gate_refuses_a_repeat_of_the_deck_or_an_earlier_card(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    drafted = {k: card("m", i) for i, k in enumerate("abcd")}
    here = {"on_topic": True, "module": MODULE.id, "reason": "same"}
    fakes.replies.append(
        {
            "verdicts": [
                {"id": "a", **here, "repeats": "b"},  # a later card: a stays
                {"id": "b", **here, "repeats": "a"},
                {"id": "c", **here, "repeats": "old"},
                {"id": "d", **here, "repeats": "d"},  # itself: ignored
            ]
        }
    )
    kept, problems = judge.gate(ctx, SCOPE, drafted, {}, {"old": card("m", 9)})
    assert list(kept) == ["a", "d"]
    assert problems == ["b: repeats a (same)", "c: repeats old (same)"]
    fakes.replies.append({"verdicts": []})
    judge.gate(ctx, SCOPE, {"a": card("m", 1)}, {}, {})
    assert "Already in the deck (id: front): (none)" in fakes.prompts[1][1]


def test_in_deck_is_this_and_earlier_modules_live_cards() -> None:
    cards = {
        "basic": card("basics", 1),
        "mine": card(MODULE.id, 1),
        "judged": card(MODULE.id, 2),
        "gone": card(MODULE.id, 3, suspended=True),
        "later": card("engine", 1),
    }
    deck = plan_context.in_deck(PLAN, MODULE, cards, {"judged"})
    assert list(deck) == ["basic", "mine"]
