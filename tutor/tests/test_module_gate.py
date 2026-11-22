# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The module gate (curriculum §6): pass a finished module before the next.

kuhy, 2026-11-22: teach a module to its end, pass every one of its cards
(plus every card of the subject due now), then the next module starts; no
daily cap and no waiting. The refusal names the exact cards that block
(``gate_cards``), so the app reviews those and nothing else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import pick as picking
from tutor.curriculum import rules
from tutor.curriculum.errors import RequestError
from tutor.tests._cur import T0, D, H, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Module


def _two(
    tmp_path: Path, *, b_status: str = "ready"
) -> tuple[Context, rules.View, list[Module]]:
    """Subject ``car``: modules a (a1, a2) and b (b1, b2), b not requiring a."""
    ctx, _ = make_ctx(tmp_path)
    found: dict[str, CardRec] = {
        "a1": card("a", 1),
        "a2": card("a", 2),
        "b1": card("b", 1),
        "b2": card("b", 2),
    }
    mods = [module("a", status="ready"), module("b", status=b_status)]
    plan = subject(ctx, modules=mods, found=found)
    return ctx, rules.View("car", plan, found, title="Cars"), mods


def _refused(
    view: rules.View, ctx: Context, card_id: str | None, now: int, skip: str = ""
) -> RequestError:
    with pytest.raises(RequestError) as err:
        picking.pick(view, ctx.fold(), card_id, now, skip)
    return err.value


def _teach_a(ctx: Context) -> None:
    taught(ctx, "car", "a1", T0, 1)
    taught(ctx, "car", "a2", T0 + 1, 2)


def test_a_taught_unreviewed_module_blocks_the_next_one(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    err = _refused(view, ctx, None, T0 + H)
    assert err.code == "no_card_left"
    assert err.extra["next"] == "review_module"
    assert err.extra["module"] == "a"
    assert err.extra["gate_cards"] == ["a1", "a2"]
    assert err.extra["writing"] is False


def test_passing_every_card_opens_the_next_module_at_once(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 3)
    err = _refused(view, ctx, None, T0 + H + 1)
    assert err.extra["gate_cards"] == ["a2"]  # a1 passed: never again
    review(ctx, "car", "a2", T0 + H + 2, 4)
    assert picking.pick(view, ctx.fold(), None, T0 + H + 3) == "b1"


def test_hard_or_again_does_not_pass_a_card(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 2)
    review(ctx, "car", "a2", T0 + H + 1, 1)
    assert _refused(view, ctx, None, T0 + H + 2).extra["gate_cards"] == ["a1", "a2"]


def test_due_cards_block_a_new_module_too(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 3)
    review(ctx, "car", "a2", T0 + H + 1, 3)
    due = ctx.fold().card("car", "a1").fsrs_state()
    assert due is not None
    err = _refused(view, ctx, None, due["due"] + 1)
    assert err.code == "no_card_left"
    assert err.extra["next"] == "reviews_due"
    assert err.extra["gate_cards"] == ["a1", "a2"]
    assert err.extra["due_at"] <= due["due"] + 1


def test_due_cards_never_block_a_started_module(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 3)
    review(ctx, "car", "a2", T0 + H + 1, 3)
    taught(ctx, "car", "b1", T0 + 2 * H, 3)
    later = T0 + 400 * D  # a1 and a2 are long due
    assert picking.pick(view, ctx.fold(), None, later) == "b2"


def test_no_daily_cap(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    many = {f"c{i}": card("a", i) for i in range(40)}
    plan = subject(ctx, modules=[module("a", status="ready")], found=many)
    view = rules.View("car", plan, many)
    for i in range(30):
        taught(ctx, "car", f"c{i}", T0 + i, i)
    assert picking.pick(view, ctx.fold(), None, T0 + 100) == "c30"


def test_a_plan_pick_of_a_later_module_names_the_review(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    err = _refused(view, ctx, "b1", T0 + H)
    assert err.code == "locked"
    assert err.extra["next"] == "review_module"
    assert err.extra["module"] == "a"
    assert err.extra["gate_cards"] == ["a1", "a2"]


def test_a_plan_pick_behind_due_cards_names_them(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 3)
    review(ctx, "car", "a2", T0 + H + 1, 3)
    err = _refused(view, ctx, "b1", T0 + 400 * D)
    assert err.code == "locked"
    assert err.extra["next"] == "reviews_due"
    assert err.extra["gate_cards"] == ["a1", "a2"]


def test_a_plan_pick_never_jumps_a_half_taught_module(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    taught(ctx, "car", "a1", T0, 1)
    review(ctx, "car", "a1", T0 + H, 3)
    err = _refused(view, ctx, "b1", T0 + H + 1)
    assert err.code == "locked"
    assert err.extra["next"] == "none"
    assert picking.pick(view, ctx.fold(), "a2", T0 + H + 1) == "a2"


def test_a_card_of_a_started_module_stays_open(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    taught(ctx, "car", "b1", T0, 1)  # b started before the gate existed
    taught(ctx, "car", "a1", T0 + 1, 2)
    assert picking.pick(view, ctx.fold(), "b2", T0 + H) == "b2"


def test_skipping_the_last_card_opens_the_review(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    taught(ctx, "car", "a1", T0, 1)
    err = _refused(view, ctx, None, T0 + H, skip="a2")
    assert err.extra["next"] == "review_module"
    assert err.extra["gate_cards"] == ["a1"]
    review(ctx, "car", "a1", T0 + H, 3)
    # Nothing to review: the skip is ignored rather than jumping to b.
    assert picking.pick(view, ctx.fold(), None, T0 + H + 1, "a2") == "a2"


def test_an_earlier_module_being_written_blocks_later_ones(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    found = {"a1": card("a", 1), "c1": card("c", 1)}
    mods = [
        module("a", status="ready"),
        module("b", status="generating"),
        module("c", status="ready"),
    ]
    plan = subject(ctx, modules=mods, found=found)
    view = rules.View("car", plan, found, title="Cars")
    taught(ctx, "car", "a1", T0, 1)
    review(ctx, "car", "a1", T0 + H, 3)
    err = _refused(view, ctx, None, T0 + H + 1)
    assert err.code == "no_card_left"
    assert err.extra["next"] != "review_module"
    assert err.extra["writing"] is True
    assert err.extra["gate_cards"] == []


def test_a_retaught_card_must_pass_again(tmp_path: Path) -> None:
    ctx, view, mods = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 3)
    review(ctx, "car", "a2", T0 + H + 1, 3)
    mods[0].status = "mastered"
    taught(ctx, "car", "a2", T0 + 2 * H, 9)  # a split / struggle re-teach
    err = _refused(view, ctx, None, T0 + 2 * H + 1)
    assert err.extra["gate_cards"] == ["a2"]


def test_flagged_cards_never_block(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    _teach_a(ctx)
    review(ctx, "car", "a1", T0 + H, 3)
    flag = {
        "dev": "p",
        "eid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "k": "flag",
        "s": "car",
        "c": "a2",
        "at": T0 + H,
        "rev": 1,
    }
    ctx.log.append([flag])
    assert picking.pick(view, ctx.fold(), None, T0 + H + 1) == "b1"


def test_the_end_of_the_plan_lists_what_is_left(tmp_path: Path) -> None:
    ctx, view, _ = _two(tmp_path)
    for i, cid in enumerate(("a1", "a2", "b1", "b2")):
        taught(ctx, "car", cid, T0 + i, i + 1)
        if cid.startswith("a"):
            review(ctx, "car", cid, T0 + H + i, 3)
    err = _refused(view, ctx, None, T0 + 2 * H)
    assert err.extra["next"] == "review_module"
    assert err.extra["module"] == "b"
    assert err.extra["gate_cards"] == ["b1", "b2"]
    review(ctx, "car", "b1", T0 + 2 * H, 3)
    review(ctx, "car", "b2", T0 + 2 * H + 1, 3)
    err = _refused(view, ctx, None, T0 + 2 * H + 2)
    assert err.extra["next"] == "reviews_due"
    assert err.extra["gate_cards"] == []  # nothing due yet: nothing to review
    due_at = err.extra["due_at"]
    assert isinstance(due_at, int)
    assert due_at > T0 + 2 * H + 2
