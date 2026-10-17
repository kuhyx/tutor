# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Undo from the Editor: restore a tutor-removed card, remove a tutor-added one."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import card_ops, card_undo
from tutor.curriculum.errors import RequestError
from tutor.curriculum.handlers import BUILD_HANDLERS
from tutor.curriculum.records import CardRec
from tutor.relay.protocol import validate
from tutor.tests._cur import T0, card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

PISTON = "https://en.wikipedia.org/wiki/Piston"
PAGE = "A piston slides up and down inside the cylinder, pushed by expanding gas."
NEW = card_ops.Draft(
    "a", "What does a piston do?", "It slides in the cylinder pushed by gas.", PISTON
)


@pytest.fixture
def car(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path)
    found = {f"a{i}": card("a", i) for i in range(1, 5)}
    found["b1"] = card("b", 1, "a1")
    found["b2"] = card("b", 2, "a2", "a1")
    mods = [module("a", status="ready", cards=4), module("b", status="ready")]
    subject(ctx, modules=mods, found=found)
    fakes.texts[PISTON] = PAGE
    return ctx, fakes


def _refused(kind: str, ctx: Context, cid: str) -> str:
    with pytest.raises(RequestError) as err:
        BUILD_HANDLERS[kind]({"subject": "car", "card": cid}, ctx)
    assert err.value.code == "edit_refused"
    return err.value.message


def test_restore_puts_the_card_and_its_requires_back(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    card_ops.remove(ctx, "car", "a1")
    gone = ctx.subjects.cards("car")
    assert gone["a1"].tutor == {"removed": T0, "requires_of": {"b1": 0, "b2": 1}}
    out = BUILD_HANDLERS["card_restore"]({"subject": "car", "card": "a1"}, ctx)
    assert out == {"card": "a1"}
    back = ctx.subjects.cards("car")
    assert not back["a1"].suspended
    assert back["a1"].tutor == {}
    assert (back["b1"].requires, back["b2"].requires) == (["a1"], ["a2", "a1"])
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 4
    assert "nothing to restore" in _refused("card_restore", ctx, "a1")


def test_restore_skips_a_dependent_that_already_has_it(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    card_ops.remove(ctx, "car", "a1")
    with_it = ctx.subjects.cards("car")
    with_it["b2"].requires = ["a1", "a2"]
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), _cards(with_it))
    card_undo.restore(ctx, "car", "a1")
    assert ctx.subjects.cards("car")["b2"].requires == ["a1", "a2"]


def _cards(found: dict[str, CardRec]) -> Any:
    from tutor.curriculum.subject_store import Change

    return Change(cards=found)


def test_restore_refusals(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    assert "unknown card" in _refused("card_restore", ctx, "zz")
    assert "nothing to restore" in _refused("card_restore", ctx, "a2")
    with pytest.raises(RequestError) as err:
        BUILD_HANDLERS["card_restore"]({"subject": "car", "card": "Bad Id"}, ctx)
    assert err.value.code == "bad_request"


def test_a_tutor_added_card_is_removed_from_the_editor(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    cid, rec = card_ops.add(ctx, "car", NEW)
    assert rec.tutor == {"added": T0}
    out = BUILD_HANDLERS["card_remove"]({"subject": "car", "card": cid}, ctx)
    assert out == {"card": cid}
    gone = ctx.subjects.cards("car")[cid]
    assert gone.suspended
    assert gone.tutor == {"added": T0, "editor_removed": T0, "requires_of": {}}
    assert "already removed" in _refused("card_remove", ctx, cid)


def test_an_editor_removal_restores_requires_exactly(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    found = ctx.subjects.cards("car")
    found["a1"].tutor = {"added": T0}  # only tutor-added cards get Remove
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), _cards(found))
    BUILD_HANDLERS["card_remove"]({"subject": "car", "card": "a1"}, ctx)
    gone = ctx.subjects.cards("car")
    assert gone["a1"].suspended
    assert gone["a1"].tutor == {
        "added": T0,
        "editor_removed": T0,
        "requires_of": {"b1": 0, "b2": 1},
    }
    assert (gone["b1"].requires, gone["b2"].requires) == ([], ["a2"])
    out = BUILD_HANDLERS["card_restore"]({"subject": "car", "card": "a1"}, ctx)
    assert out == {"card": "a1"}
    back = ctx.subjects.cards("car")
    assert not back["a1"].suspended
    assert back["a1"].tutor == {"added": T0}  # Remove is offered again
    assert (back["b1"].requires, back["b2"].requires) == (["a1"], ["a2", "a1"])
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 4


def test_restore_of_an_older_editor_removal_only_unsuspends(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    found = ctx.subjects.cards("car")
    # Removed before the Editor recorded anything: suspended, tutor-added.
    found["a1"].tutor = {"added": T0}
    found["a1"].suspended = True
    found["b1"].requires = []
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), _cards(found))
    BUILD_HANDLERS["card_restore"]({"subject": "car", "card": "a1"}, ctx)
    back = ctx.subjects.cards("car")
    assert not back["a1"].suspended
    assert back["a1"].tutor == {"added": T0}
    assert back["b1"].requires == []  # no record, so no requires to put back
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 4


def test_restore_still_refuses_a_card_nobody_removed_by_hand(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    found = ctx.subjects.cards("car")
    found["a2"].suspended = True  # e.g. a regen suspend: no mark at all
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), _cards(found))
    assert "nothing to restore" in _refused("card_restore", ctx, "a2")


def test_the_editor_removes_only_tutor_cards_and_keeps_three(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    assert "only a card the tutor added" in _refused("card_remove", ctx, "a1")
    cid, _ = card_ops.add(ctx, "car", NEW)
    card_ops.remove(ctx, "car", "a1")
    card_ops.remove(ctx, "car", "a2")
    assert "3 live cards" in _refused("card_remove", ctx, cid)


def test_card_json_keeps_the_old_shape_until_the_tutor_touches_it() -> None:
    plain = card("a", 1)
    assert "tutor" not in plain.to_json()
    marked = card("a", 1, tutor={"added": 5})
    assert marked.to_json()["tutor"] == {"added": 5}
    assert CardRec.from_json(marked.to_json()) == marked


@pytest.mark.parametrize("kind", ["card_restore", "card_remove"])
def test_relay_kinds(kind: str) -> None:
    req = {"kind": kind, "dev": "0" * 8 + "-0000-0000-0000-" + "0" * 12}
    body = {"subject": "car", "card": "a1", "junk": 1}
    got = validate("0" * 26, {**req, "created": 1, "body": body})
    assert (got.lane, got.body) == ("build", {"subject": "car", "card": "a1"})


def test_restore_refused_when_it_would_make_a_cycle(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    card_ops.remove(ctx, "car", "a1")
    found = ctx.subjects.cards("car")
    found["a1"].requires = ["b1"]  # an Editor edit since: a1 now needs b1
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), _cards(found))
    assert "cycle" in _refused("card_restore", ctx, "a1")
    assert ctx.subjects.cards("car")["a1"].suspended
