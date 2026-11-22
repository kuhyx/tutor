# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The module gate under C3: the guard's unit order beats the plan order.

The module gate (``test_module_gate.py``) opens a module only once every
earlier plan module is fully taught; C3 (``test_theory_phase.py``) lets the
tutor teach only the guard's current unit. The unit order starts at a module
that is not the plan's first, so the two together shut the one teachable
module for good. The rule (``pick.unit_order_wins``): an earlier module C3
refuses now is not counted as "still to teach". Its taught cards gate as
before, and an ungated subject keeps the plan order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum.errors import LOCKED, NO_CARD_LEFT, RequestError
from tutor.curriculum.source import SubjectSource
from tutor.store import Store
from tutor.tests._cur import T0, Fakes, H, card, make_ctx, module, review, subject
from tutor.tests._cur import taught as teach
from tutor.tests._phase import LC, SQL, grant

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context


def _src(tmp_path: Path, name: str = LC) -> tuple[Context, SubjectSource, Fakes]:
    """Plan order a (a0, a1), b (b0): the guard's unit order starts at b."""
    ctx, fakes = make_ctx(tmp_path)
    mods = [module("a", status="ready"), module("b", status="ready")]
    found = {"a0": card("a", 0), "a1": card("a", 1), "b0": card("b", 0)}
    subject(ctx, name, modules=mods, found=found)
    return ctx, SubjectSource(Store(tmp_path), ctx, name), fakes


def _refusal(src: SubjectSource, card_id: str | None) -> RequestError:
    with pytest.raises(RequestError) as err:
        src.pick(card_id)
    return err.value


def test_a_refused_earlier_module_never_holds_the_teachable_one(
    tmp_path: Path,
) -> None:
    grant((LC, "b"))  # THEORY(b); a comes first in the plan and is refused
    _, src, _ = _src(tmp_path)
    assert src.pick(None, module="b").id == "b0"  # what /learn/<LC>/b picks
    assert src.pick("b0").id == "b0"  # Engine.start picks it again, by id
    assert _refusal(src, "a0").code == NO_CARD_LEFT  # C3 itself is untouched


@pytest.mark.parametrize("name", [SQL, "car"])
def test_an_ungated_subject_keeps_the_plan_order(name: str, tmp_path: Path) -> None:
    grant((LC, "b"))  # never read: the subject is not gated
    _, src, _ = _src(tmp_path, name)
    err = _refusal(src, "b0")
    assert err.code == LOCKED
    assert err.extra["next"] == "none"
    assert err.extra["gate_cards"] == []
    assert "opens once earlier modules are taught" in str(err)
    assert src.pick(None).id == "a0"


def test_a_teachable_earlier_module_still_holds_the_next_one(tmp_path: Path) -> None:
    grant((LC, "a"), (LC, "b"))  # one unit of two modules: the plan orders them
    _, src, _ = _src(tmp_path)
    err = _refusal(src, "b0")
    assert (err.code, err.extra["next"], err.extra["gate_cards"]) == (
        LOCKED,
        "none",
        [],
    )
    assert src.pick(None).id == "a0"


def test_an_unreviewed_taught_card_of_a_refused_module_still_gates(
    tmp_path: Path,
) -> None:
    ctx, src, _ = _src(tmp_path)
    teach(ctx, LC, "a0", T0, 1)  # taught before the phase moved to b
    grant((LC, "b"))
    err = _refusal(src, "b0")
    assert (err.code, err.extra["next"], err.extra["module"]) == (
        LOCKED,
        "review_module",
        "a",
    )
    assert err.extra["gate_cards"] == ["a0"]  # a1 is untaught: nothing to review
    nxt = _refusal(src, None)
    assert (nxt.code, nxt.extra["gate_cards"]) == (NO_CARD_LEFT, ["a0"])
    review(ctx, LC, "a0", T0 + H, 3)
    assert src.pick("b0").id == "b0"
    assert src.pick(None).id == "b0"


def test_due_reviews_of_taught_cards_still_block_in_a_gated_subject(
    tmp_path: Path,
) -> None:
    ctx, src, fakes = _src(tmp_path)
    teach(ctx, LC, "a0", T0, 1)
    review(ctx, LC, "a0", T0 + H, 3)
    grant((LC, "b"))
    state = ctx.fold().card(LC, "a0").fsrs_state()
    assert state is not None
    fakes.now[0] = state["due"] + 1  # a0 passed once, and is due again
    err = _refusal(src, "b0")
    assert (err.code, err.extra["next"]) == (LOCKED, "reviews_due")
    assert err.extra["gate_cards"] == ["a0"]
    nxt = _refusal(src, None)
    assert (nxt.code, nxt.extra["next"]) == (NO_CARD_LEFT, "reviews_due")
    assert nxt.extra["gate_cards"] == ["a0"]
