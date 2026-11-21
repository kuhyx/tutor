# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Vetting drafted cards: code checks, the judge, three repair rounds, drop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.curriculum import quality, quality_judge, vet, wiki
from tutor.curriculum.plan_context import Scope
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

FOUND = [wiki.Source("https://en.wikipedia.org/wiki/A", "A", "text a")]


def item(cid: str, front: str = "", **over: Any) -> dict[str, Any]:
    base = {
        "id": cid,
        "front": front or f"What does {cid} do?",
        "back": "It turns.",
        "mnemonic": "",
        "source": 1,
        "excerpt": "the part turns the crank shaft round and round",
        "requires": [],
    }
    return {**base, **over}


def ok(*ids: str) -> dict[str, Any]:
    return {"verdicts": [{"id": i, "broken": [], "why": ""} for i in ids]}


def _batch(tmp_path: Path, **kw: Any) -> tuple[Context, Fakes, vet.Batch]:
    ctx, fakes = make_ctx(tmp_path)
    fakes.auto_judge = False
    plan = subject(ctx, modules=[module("a", status="generating"), module("b", "a")])
    scope = Scope(ctx.subjects.need_meta("car"), plan.modules[0], plan)
    return ctx, fakes, vet.Batch(scope, FOUND, **kw)


def test_clean_cards_pass_after_one_judge_call(tmp_path: Path) -> None:
    ctx, fakes, batch = _batch(tmp_path)
    fakes.replies = [ok("one", "two")]
    out = vet.vet(ctx, batch, [item("one"), item("two")])
    assert list(out.kept) == ["one", "two"]
    assert (out.dropped, out.rounds) == ([], 0)
    assert quality.RULES in fakes.prompts[0][0]


def test_a_two_question_card_is_repaired_into_two(tmp_path: Path) -> None:
    ctx, fakes, batch = _batch(tmp_path)
    double = item("both", "What is a crank, and what does it turn?")
    fixed = [
        item("both", "What is a crank?", fixes="both"),
        item("both-turns", "What does a crank turn?", fixes="both"),
        item("stray", fixes="unknown"),
    ]
    fakes.replies = [ok("fine"), {"cards": fixed}, ok("both", "both-turns")]
    out = vet.vet(ctx, batch, [item("fine"), double])
    assert list(out.kept) == ["fine", "both", "both-turns"]
    assert (out.dropped, out.rounds) == ([], 1)
    repair_prompt = fakes.prompts[1][1]
    assert "one_question" in repair_prompt
    assert '<source n="1"' in repair_prompt


def test_the_judge_fails_a_card_and_three_repairs_then_drop(tmp_path: Path) -> None:
    ctx, fakes, batch = _batch(tmp_path)
    bad = {"verdicts": [{"id": "x", "broken": ["unguessable"], "why": "a port"}]}
    again = {"cards": [item("x", fixes="x")]}
    fakes.replies = [bad, again, bad, again, bad, again, bad]
    out = vet.vet(ctx, batch, [item("x")])
    assert out.kept == {}
    assert out.rounds == vet.REPAIR_ROUNDS
    assert out.dropped == ["x: unguessable: a port"]
    assert fakes.replies == []


def test_structural_refusals_and_missing_verdicts(tmp_path: Path) -> None:
    ctx, fakes, batch = _batch(tmp_path)
    fakes.bad_excerpts = {"this one is not in the page at all ok"}
    items: list[object] = [
        "junk",
        item("nosrc", source=9),
        item("long", back="word " * 31),
        item("lie", excerpt="this one is not in the page at all ok"),
        item("quiet"),
        {"front": "No id here?", "source": 5},
    ]
    fakes.replies = [{"verdicts": "none"}, {"cards": "none"}]
    out = vet.vet(ctx, batch, items)
    assert out.kept == {}
    assert [d.split(":")[0] for d in out.dropped] == [
        "card-0",
        "nosrc",
        "long",
        "lie",
        "card-5",
        "quiet",
    ]
    assert "no_verdict" in out.dropped[-1]


def test_hard_cards_need_a_mnemonic_and_ids_stay_free(tmp_path: Path) -> None:
    ctx, fakes, batch = _batch(tmp_path, taken=frozenset({"a"}), hard=frozenset({"h"}))
    fakes.replies = [
        ok("a-2"),
        {"cards": [item("h", mnemonic="Turn the crank like a key", fixes="h")]},
        ok("h"),
    ]
    out = vet.vet(ctx, batch, [item("a"), item("h")])
    assert list(out.kept) == ["a-2", "h"]
    assert out.kept["h"].mnemonic == "Turn the crank like a key"
    assert '"hard": true' in fakes.prompts[2][1]


def test_the_limit_caps_drafts_and_repairs(tmp_path: Path) -> None:
    ctx, fakes, batch = _batch(tmp_path, limit=1)
    fakes.replies = [ok("one")]
    out = vet.vet(ctx, batch, [item("one"), item("two")])
    assert list(out.kept) == ["one"]


def test_judge_edges(tmp_path: Path) -> None:
    ctx, fakes, _ = _batch(tmp_path)
    assert quality_judge.judge(ctx, "about", {}, set()) == {}
    cards = {"a": card("a", 1), "b": card("a", 2), "c": card("a", 3)}
    fakes.replies = [
        {
            "verdicts": [
                "junk",
                {"id": "zzz", "broken": []},
                {"id": "a", "broken": ["hedged", "made-up"], "why": "usually"},
                {"id": "b", "broken": "no"},
            ]
        }
    ]
    said = quality_judge.judge(ctx, "about", cards, set())
    assert said["a"] == [quality.Problem("hedged", "usually")]
    assert said["b"][0].rule == quality_judge.NO_VERDICT
    assert said["c"][0].rule == quality_judge.NO_VERDICT


def test_as_item_numbers_the_source() -> None:
    rec = card("a", 1, source=FOUND[0].url, mnemonic="m")
    assert vet.as_item("x", rec, FOUND)["source"] == 1
    assert vet.as_item("x", card("a", 1), FOUND)["source"] == 0
