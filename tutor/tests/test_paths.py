# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Interrogation paths: written per card rev, PC-only, suggestions to the tutor."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from tutor import path_prompt
from tutor.cards import Card, Topic
from tutor.curriculum import paths
from tutor.curriculum.deck_source import DeckSource
from tutor.curriculum.source import SubjectSource
from tutor.curriculum.subject_store import Change
from tutor.prompt import system_prompt
from tutor.store import Store
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes


def path(cid: str, **over: Any) -> dict[str, Any]:
    base = {
        "id": cid,
        "opening": "What do you think turns the wheels?",
        "probes": ["What if the clutch is open?"],
        "misconception": "The engine turns the wheels directly.",
        "correction": "The gearbox sits between them.",
        "hints": ["Think of a bicycle chain.", "Something sits in between."],
        "tell": ["It is called a gearbox."],
        "pass_criterion": "Names the gearbox as the link.",
        "typed_follow_up": False,
    }
    return {**base, **over}


def _car(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", "a"), module("c", "b")]
    found = {"x": card("a", 1), "y": card("a", 2), "z": card("b", 1)}
    found["gone"] = card("a", 3, suspended=True)
    subject(ctx, modules=mods, found=found)
    return ctx, fakes


def test_write_stores_a_path_per_card_rev(tmp_path: Path) -> None:
    ctx, fakes = _car(tmp_path)
    assert paths.pending(ctx) == [("car", "a")]  # b is locked, gone is suspended
    fakes.replies = [{"paths": [path("x"), path("y"), path("zzz"), "junk"]}]
    assert paths.write(ctx, "car", "a") == 2
    system, prompt = fakes.prompts[0]
    assert system == paths.SYSTEM
    assert '"id": "x"' in prompt
    assert "gone" not in prompt
    got = paths.fresh(ctx, "car", "x")
    assert got is not None
    assert got["typed_follow_up"] is False
    assert "id" not in got
    assert paths.pending(ctx) == []
    assert paths.write(ctx, "car", "a") == 0  # nothing stale: no call
    assert paths.write(ctx, "car", "nope") == 0


def test_a_rev_change_makes_the_path_stale(tmp_path: Path) -> None:
    ctx, fakes = _car(tmp_path)
    fakes.replies = [{"paths": [path("x"), path("y")]}]
    paths.write(ctx, "car", "a")
    found = ctx.subjects.cards("car")
    found["x"] = replace(found["x"], rev=2, front="What links engine and wheels?")
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(cards=found))
    assert paths.fresh(ctx, "car", "x") is None
    assert paths.fresh(ctx, "car", "y") is not None
    assert paths.stale(ctx, "car", "a") == ["x"]
    fakes.replies = [{"paths": [path("x", opening="What links them?")]}]
    assert paths.write(ctx, "car", "a") == 1
    assert (paths.fresh(ctx, "car", "x") or {})["opening"] == "What links them?"
    assert paths.fresh(ctx, "car", "y") is not None  # kept


def test_paths_are_pc_only_and_tolerate_junk(tmp_path: Path) -> None:
    ctx, fakes = _car(tmp_path)
    assert paths.load(ctx, "car") == {}
    assert paths.fresh(ctx, "car", "nope") is None
    fakes.replies = [{"paths": "none"}]
    assert paths.write(ctx, "car", "a") == 0
    where = tmp_path / "subjects/car/paths.json"
    where.write_text('["not a map"]')
    assert paths.load(ctx, "car") == {}
    where.write_text('{"x": {"rev": 1, "path": "junk"}, "y": 3}')
    assert paths.fresh(ctx, "car", "x") is None
    assert "paths" not in (tmp_path / "subjects/car/cards.json").read_text()
    subject(ctx, "draft", plan_status="draft")
    assert paths.pending(ctx) == [("car", "a")]


def test_clean_trims_and_refuses_empty() -> None:
    assert paths.clean("junk") is None
    assert paths.clean(path("x", opening=" ")) is None
    got = paths.clean(path("x", probes="no", hints=["a", "", "b", "c", "d", "e"]))
    assert got is not None
    assert (got["probes"], len(got["hints"])) == ([], 4)
    assert (paths.clean({"opening": "o", "pass_criterion": "p"}) or {})[
        "typed_follow_up"
    ]


def test_the_tutor_reads_the_path_as_suggestions() -> None:
    target = Card(
        "x", "Q?", "A.", "https://e.org", "an excerpt", Topic("t", "T", ("",))
    )
    plain = system_prompt(target, [])
    assert "interrogation path" not in plain
    text = system_prompt(target, [], path=paths.clean(path("x")))
    assert "SUGGESTIONS, not a script" in text
    assert "react to what they actually wrote" in text
    assert "opening question: What do you think turns the wheels?" in text
    assert "- It is called a gearbox." in text
    assert path_prompt.NO_TYPED in text
    assert text.index("# Target card") < text.index("# Suggested interrogation path")
    typed = path_prompt.section({**path("x"), "typed_follow_up": True, "tell": []})
    assert path_prompt.TYPED in typed
    assert "never ask the learner to guess" not in typed
    bare = path_prompt.section({"opening": "o", "pass_criterion": "p"})
    assert "misconception" not in bare


def test_sources_hand_the_fresh_path_to_the_engine(tmp_path: Path) -> None:
    ctx, fakes = _car(tmp_path)
    src = SubjectSource(Store(tmp_path), ctx, "car")
    assert src.path("x") is None
    fakes.replies = [{"paths": [path("x")]}]
    paths.write(ctx, "car", "a")
    assert (src.path("x") or {})["opening"].startswith("What do you think")
    assert DeckSource(Store(tmp_path), deck=[]).path("x") is None
