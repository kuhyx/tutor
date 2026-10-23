# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The ``mnemonic`` and ``split`` card edits, the split's undo and its cap (struggle §1/§2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import card_ops, card_split, card_undo, rules
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import T0, card, taught
from tutor.tests.test_card_ops import BACK, FRONT, PAGE, PISTON, car_subject, refused

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

THING = "https://en.wikipedia.org/wiki/Thing"  # every car card's source
KIND_F, KIND_B = "What kind of engine has a piston?", "A reciprocating engine."
KIND = card_split.Part(KIND_F, KIND_B, PISTON, "component of reciprocating engines")
SLIDES = card_split.Part(FRONT, BACK, "", "")  # "": the original's source
IDS = ["what-kind-of-engine-has-a-piston", "what-does-a-piston-do-in-an-engine"]
SLIDES_EXCERPT = (
    "It slides up and down inside the cylinder, pushed by the expanding gas "
    "of the burning fuel."
)


@pytest.fixture
def car(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = car_subject(tmp_path)
    fakes.texts[THING] = PAGE
    return ctx, fakes


def _snapshot(ctx: Context) -> dict[str, object]:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    cards = {k: v.to_json() for k, v in ctx.subjects.cards("car").items()}
    return {"cards": cards, "counts": [m.cards for m in plan.modules]}


def test_mnemonic_sets_bumps_rev_and_clears(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    rec = card_ops.mnemonic(ctx, "car", "a1", " Piston:\n pushed  by gas. ")
    assert (rec.mnemonic, rec.rev) == ("Piston: pushed by gas.", 2)
    assert (
        "already"
        in refused(
            lambda: card_ops.mnemonic(ctx, "car", "a1", "Piston: pushed by gas.")
        ).message
    )
    assert (
        "over 40 words"
        in refused(lambda: card_ops.mnemonic(ctx, "car", "a1", "w " * 41)).message
    )
    rec = card_ops.mnemonic(ctx, "car", "a1", "")
    assert (rec.mnemonic, rec.rev) == ("", 3)


def test_split_suspends_the_original_and_slots_new_cards(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    taught(ctx, "car", "a1", T0)
    original, ids = card_split.split(ctx, "car", "a1", [KIND, SLIDES])
    assert ids == IDS
    found = ctx.subjects.cards("car")
    assert found["a1"].suspended
    assert original.front == found["a1"].front
    first, second = found[IDS[0]], found[IDS[1]]
    assert (first.module, first.split_of, first.origin, first.rev) == (
        "a",
        "a1",
        "edited",
        1,
    )
    assert (first.source, second.source) == (PISTON, THING)
    assert second.excerpt == SLIDES_EXCERPT
    assert first.requires == second.requires == found["a1"].requires
    order = sorted((c.order, k) for k, c in found.items() if c.module == "a")
    assert [k for _, k in order] == ["a1", *IDS, "a2", "a3", "a4"]
    assert found["b1"].requires == IDS  # the dependents need both halves now
    assert found["b2"].requires == [*IDS, "a2"]
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 5


def test_a_failing_child_changes_nothing(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    before = _snapshot(ctx)
    fakes.bad_excerpts.add(SLIDES_EXCERPT)
    err = refused(lambda: card_split.split(ctx, "car", "a1", [KIND, SLIDES]))
    assert "excerpt check failed" in err.message
    assert _snapshot(ctx) == before
    long = card_split.Part("w " * 26 + "?", KIND_B, PISTON, KIND.quote)
    err = refused(lambda: card_split.split(ctx, "car", "a1", [KIND, long]))
    assert "front is over" in err.message
    assert _snapshot(ctx) == before
    empty = card_split.Part("", "", "", "")
    assert (
        "front and back"
        in refused(lambda: card_split.split(ctx, "car", "a1", [KIND, empty])).message
    )
    assert _snapshot(ctx) == before


def test_split_refusals(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    for parts in ([KIND], [KIND, SLIDES, KIND, SLIDES, KIND]):
        assert (
            "2-4"
            in refused(lambda p=parts: card_split.split(ctx, "car", "a1", p)).message
        )
    assert (
        "unknown card"
        in refused(lambda: card_split.split(ctx, "car", "zz", [KIND, SLIDES])).message
    )
    card_ops.remove(ctx, "car", "a4")
    assert (
        "removed"
        in refused(lambda: card_split.split(ctx, "car", "a4", [KIND, SLIDES])).message
    )


def test_split_never_reuses_an_id(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    cards = ctx.subjects.cards("car")
    cards[IDS[0]] = card("a", 9, suspended=True)
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(cards=cards))
    _, ids = card_split.split(ctx, "car", "a1", [KIND, SLIDES])
    assert ids == [f"{IDS[0]}-2", IDS[1]]


def test_restore_reverts_the_whole_split(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    before = _snapshot(ctx)
    card_split.split(ctx, "car", "a1", [KIND, SLIDES])
    assert card_undo.card_restore({"subject": "car", "card": "a1"}, ctx) == {
        "card": "a1"
    }
    found = ctx.subjects.cards("car")
    assert not found["a1"].suspended
    assert all(found[i].suspended for i in IDS)
    assert (found["b1"].requires, found["b2"].requires) == (["a1"], ["a1", "a2"])
    assert _snapshot(ctx)["counts"] == before["counts"]
    assert (
        "nothing to restore"
        in refused(
            lambda: card_undo.card_restore({"subject": "car", "card": IDS[0]}, ctx)
        ).message
    )


def test_a_split_child_is_exempt_from_the_new_cap(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    taught(ctx, "car", "a1", T0)
    _, ids = card_split.split(ctx, "car", "a1", [KIND, SLIDES])
    ctx.log.append(
        [
            {"dev": "p", "eid": "01M4RBCX52MMHCK7K73E6KV9AA", "k": "new_cap"}
            | {"n": 1, "at": T0 - 1}
        ]
    )
    plan = ctx.subjects.plan("car")
    assert plan is not None
    view = rules.View("car", plan, ctx.subjects.cards("car"))
    assert rules.pick(view, ctx.fold(), None, T0 + 10) == ids[0]  # 1 new today
    with pytest.raises(ValueError, match="daily"):
        rules.pick(view, ctx.fold(), "a2", T0 + 10)
