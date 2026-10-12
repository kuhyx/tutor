# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The model's relevance calls: titles, source pick, the per-card gate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.curriculum import judge
from tutor.curriculum.records import Meta, Module
from tutor.curriculum.wiki import WIKIPEDIA, Page
from tutor.tests._cur import card, make_ctx

if TYPE_CHECKING:
    from pathlib import Path

META = Meta("How a car works", "I want to learn how a car works", "active", 0)
MODULE = Module("car-overview", "Car", "The main systems of a car.")
PAGES = [Page(WIKIPEDIA, f"P{i}", "word " * 300, exact=True) for i in range(1, 5)]


def test_propose_titles(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies += [
        {"titles": [" Car ", "", 3, "Engine", "A", "B", "C", "D"]},
        {"titles": "Car"},
    ]
    assert judge.propose_titles(ctx, META, MODULE) == ["Car", "Engine", "A", "B", "C"]
    assert judge.propose_titles(ctx, META, MODULE) == []
    system, prompt = fakes.prompts[0]
    assert system == judge.TITLES_SYSTEM
    assert "Learner's goal: I want to learn how a car works" in prompt


def test_pick_sources(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    assert judge.pick_sources(ctx, META, MODULE, [], 3) == []
    assert not fakes.prompts  # no candidates: no model call
    fakes.replies += [
        {"keep": [3, True, 0, 9, 3, "1", 1, 2, 4], "why": ""},
        {"keep": None, "why": ""},
    ]
    picked = judge.pick_sources(ctx, META, MODULE, PAGES, 3)
    assert [p.title for p in picked] == ["P3", "P1", "P2"]
    assert judge.pick_sources(ctx, META, MODULE, PAGES, 3) == []
    prompt = fakes.prompts[0][1]
    assert (
        '<candidate n="2" title="P2" url="https://en.wikipedia.org/wiki/P2">' in prompt
    )
    assert len(prompt.split("</candidate>")[0].split()) < judge.LEAD_WORDS + 40


def test_gate_fails_closed(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    assert judge.gate(ctx, META, MODULE, {}, {}) == ({}, [])
    drafted = {"a": card("m", 1), "b": card("m", 2), "c": card("m", 3)}
    fakes.replies.append(
        {
            "verdicts": [
                {"id": "a", "on_topic": True, "reason": "parts"},
                {"id": "b", "on_topic": False, "reason": "toy car"},
                {"id": 7, "on_topic": True},
                "junk",
            ]
        }
    )
    titles = {"https://en.wikipedia.org/wiki/Thing": "Thing"}
    kept, problems = judge.gate(ctx, META, MODULE, drafted, titles)
    assert list(kept) == ["a"]
    assert problems == ["b: off topic (toy car)", "c: off topic (no verdict)"]
    assert '"source": "Thing"' in fakes.prompts[0][1]
    fakes.replies.append({"verdicts": {}})
    assert judge.gate(ctx, META, MODULE, {"a": card("m", 1)}, {})[0] == {}
