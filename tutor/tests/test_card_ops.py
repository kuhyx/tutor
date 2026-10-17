# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's own card edits: rewrite, add (server-quoted excerpt), remove."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import card_ops
from tutor.curriculum.errors import RequestError
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

PISTON = "https://en.wikipedia.org/wiki/Piston"
PAGE = (
    "A piston is a component of reciprocating engines. It slides up and down "
    "inside the cylinder,[3] pushed by the expanding gas of the burning fuel. "
    "Cats and dogs are popular pets in many households around the world."
)
FRONT = "What does a piston do in an engine?"
BACK = "It slides up and down in the cylinder, pushed by the expanding gas."


@pytest.fixture
def car(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path)
    found = {f"a{i}": card("a", i) for i in range(1, 5)}
    found["b1"] = card("b", 1, "a1")
    found["b2"] = card("b", 2, "a1", "a2")
    mods = [
        module("a", status="ready", cards=4),
        module("b", "a", status="ready", cards=2),
    ]
    subject(ctx, modules=mods, found=found)
    fakes.texts[PISTON] = PAGE
    return ctx, fakes


def _refused(call: object) -> RequestError:
    assert callable(call)
    with pytest.raises(RequestError) as err:
        call()
    assert err.value.code == "edit_refused"
    return err.value


def test_rewrite_keeps_source_and_excerpt(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    before = ctx.subjects.cards("car")["a1"]
    rec = card_ops.rewrite(ctx, "car", "a1", front="What is thing one?", back="")
    after = ctx.subjects.cards("car")["a1"]
    assert rec == after
    assert (after.front, after.back) == ("What is thing one?", before.back)
    assert (after.source, after.excerpt) == (before.source, before.excerpt)
    assert (after.requires, after.rev, after.origin) == (before.requires, 2, "edited")


def test_rewrite_refusals(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    assert (
        "unknown card"
        in _refused(
            lambda: card_ops.rewrite(ctx, "car", "zz", front="x", back="y")
        ).message
    )
    long = "word " * 31
    assert (
        "over 30 words"
        in _refused(
            lambda: card_ops.rewrite(ctx, "car", "a1", front="", back=long)
        ).message
    )
    assert ctx.subjects.cards("car")["a1"].rev == 1


def test_add_quotes_the_supporting_sentence(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    cid, rec = card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, PISTON))
    assert cid == "what-does-a-piston-do-in-an-engine"
    assert rec.excerpt == (
        "It slides up and down inside the cylinder, pushed by the expanding gas "
        "of the burning fuel."
    )
    stored = ctx.subjects.cards("car")[cid]
    assert (stored.module, stored.source, stored.order) == ("a", PISTON, 5)
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 5


def test_add_finds_the_module_by_title(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    cid, rec = card_ops.add(ctx, "car", card_ops.Draft(" B ", FRONT, BACK, PISTON))
    assert rec.module == "b"
    assert cid in ctx.subjects.cards("car")


def test_add_refused_when_no_sentence_supports_it(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    fakes.texts[PISTON] = "Cats and dogs are popular pets in many households."
    err = _refused(
        lambda: card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, PISTON))
    )
    assert "no sentence" in err.message
    assert PISTON in err.message
    assert len(ctx.subjects.cards("car")) == 6


def test_add_refused_when_the_page_cannot_be_read(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    url = "https://example.org/missing"
    err = _refused(
        lambda: card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, url))
    )
    assert "cannot read" in err.message


def test_add_still_runs_the_excerpt_check(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    fakes.bad_excerpts.add(
        "It slides up and down inside the cylinder, pushed by the expanding gas "
        "of the burning fuel."
    )
    err = _refused(
        lambda: card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, PISTON))
    )
    assert "excerpt check failed" in err.message


def test_add_refusals(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    assert (
        "unknown topic"
        in _refused(
            lambda: card_ops.add(ctx, "car", card_ops.Draft("zz", FRONT, BACK, PISTON))
        ).message
    )
    assert (
        "https"
        in _refused(
            lambda: card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, "ftp:x"))
        ).message
    )


def test_remove_suspends_and_drops_requires(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    rec = card_ops.remove(ctx, "car", "a1")
    found = ctx.subjects.cards("car")
    assert rec.suspended
    assert found["a1"].suspended
    assert (found["b1"].requires, found["b2"].requires) == ([], ["a2"])
    assert (found["b1"].rev, found["b2"].rev) == (1, 1)  # flags stay
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 3
    assert plan.modules[0].status == "ready"


def test_remove_refused_below_three_live_cards(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    card_ops.remove(ctx, "car", "a1")
    err = _refused(lambda: card_ops.remove(ctx, "car", "a2"))
    assert "3 live cards" in err.message
    assert not ctx.subjects.cards("car")["a2"].suspended


def test_remove_refusals(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    card_ops.remove(ctx, "car", "a4")
    assert "unknown card" in _refused(lambda: card_ops.remove(ctx, "car", "z")).message
    assert (
        "already removed" in _refused(lambda: card_ops.remove(ctx, "car", "a4")).message
    )


def test_a_long_sentence_is_quoted_as_a_window(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    filler = " ".join(f"w{i}" for i in range(50))
    fakes.texts[PISTON] = f"{filler} the piston slides in the cylinder pushed by gas."
    _, rec = card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, PISTON))
    assert len(rec.excerpt.split()) == 40
    assert rec.excerpt.endswith("the piston slides in the cylinder pushed by gas.")


def test_add_refused_without_a_plan(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx)
    (tmp_path / "subjects" / "car" / "plan.json").unlink()
    err = _refused(
        lambda: card_ops.add(ctx, "car", card_ops.Draft("a", FRONT, BACK, PISTON))
    )
    assert "no plan" in err.message


def test_an_edit_that_changes_nothing_is_refused(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    old = ctx.subjects.cards("car")["a1"]
    for front, back in (("", ""), (old.front, f" {old.back} ")):
        err = _refused(
            lambda f=front, b=back: card_ops.rewrite(ctx, "car", "a1", front=f, back=b)
        )
        assert "changes nothing" in err.message
    assert ctx.subjects.cards("car")["a1"].rev == 1  # the learner's flags stay


def test_a_quote_hint_finds_the_sentence_across_languages(
    car: tuple[Context, Fakes],
) -> None:
    # A Polish card from an English page: the back shares no word with it.
    ctx, _ = car
    front, back = (
        "Co robi tłok w silniku?",
        "Porusza się w cylindrze, pchany przez gaz.",
    )
    pl = card_ops.Draft("a", front, back, PISTON)
    assert "no sentence" in _refused(lambda: card_ops.add(ctx, "car", pl)).message
    hint = "the piston slides up and down in the cylinder pushed by gas"
    _, rec = card_ops.add(ctx, "car", card_ops.Draft("a", front, back, PISTON, hint))
    assert rec.excerpt.startswith("It slides up and down inside the cylinder")
