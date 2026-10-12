# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Unlock, mastery, recall, the daily cap and the next-card pick (§6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import rules
from tutor.curriculum.errors import RequestError
from tutor.tests._cur import T0, D, H, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec, Plan


def _setup(tmp_path: Path) -> tuple[Context, Plan, dict[str, CardRec]]:
    ctx, _ = make_ctx(tmp_path)
    found = {"a1": card("a", 1), "a2": card("a", 2, "a1"), "b1": card("b", 1)}
    plan = subject(ctx, found=found)
    return ctx, plan, found


def _view(ctx: Context) -> rules.View:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    return rules.View("car", plan, ctx.subjects.cards("car"))


def test_good_needs_20h_and_good_rating(tmp_path: Path) -> None:
    ctx, _, _ = _setup(tmp_path)
    taught(ctx, "car", "a1", T0)
    assert not rules.good(ctx.fold().card("car", "a1"))
    review(ctx, "car", "a1", T0 + 19 * H, 4)
    assert not rules.good(ctx.fold().card("car", "a1"))
    review(ctx, "car", "a1", T0 + 20 * H, 3)
    assert rules.good(ctx.fold().card("car", "a1"))
    review(ctx, "car", "a1", T0 + D, 2)
    assert not rules.good(ctx.fold().card("car", "a1"))


def test_recall_skips_flagged_and_suspended(tmp_path: Path) -> None:
    ctx, plan, found = _setup(tmp_path)
    found["a2"].suspended = True
    view = rules.View("car", plan, found)
    assert rules.recall(view, "a", ctx.fold()) == 0.0
    taught(ctx, "car", "a1", T0)
    review(ctx, "car", "a1", T0 + D, 3)
    assert rules.recall(view, "a", ctx.fold()) == 1.0
    assert rules.recall(view, "zzz", ctx.fold()) == 0.0
    ctx.log.append(
        [
            {
                "dev": "p",
                "eid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "k": "flag",
                "s": "car",
                "c": "a1",
                "at": T0,
                "rev": 1,
            }
        ]
    )
    assert rules.recall(view, "a", ctx.fold()) == 0.0


def test_advance_masters_and_unlocks_in_one_pass(tmp_path: Path) -> None:
    ctx, _, _ = _setup(tmp_path)
    for i, cid in enumerate(("a1", "a2")):
        taught(ctx, "car", cid, T0 + i, i)
        review(ctx, "car", cid, T0 + D + i, 3)
    view = _view(ctx)
    assert rules.advance_statuses(view, ctx.fold()) == ["b"]
    assert [m.status for m in view.plan.modules] == ["mastered", "generating", "locked"]
    assert not rules.completed(view.plan)
    for m in view.plan.modules:
        m.status = "mastered"
    assert rules.completed(view.plan)


def test_nothing_unlocks_before_approval(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, plan_status="draft", modules=[module("a"), module("b"), module("c")])
    view = _view(ctx)
    assert rules.advance_statuses(view, ctx.fold()) == []


def test_a_module_with_a_taught_card_stays_unlocked(tmp_path: Path) -> None:
    ctx, plan, found = _setup(tmp_path)
    plan.modules[1].status = "ready"
    taught(ctx, "car", "b1", T0)
    assert rules.unlocked(rules.View("car", plan, found), plan.modules[1], ctx.fold())


def test_pick_order_gating_and_errors(tmp_path: Path) -> None:
    ctx, _, _ = _setup(tmp_path)
    view = _view(ctx)
    assert rules.pick(view, ctx.fold(), None, T0) == "a1"
    with pytest.raises(RequestError, match="locked") as err:
        rules.pick(view, ctx.fold(), "a2", T0)
    assert err.value.code == "locked"
    with pytest.raises(RequestError) as err:
        rules.pick(view, ctx.fold(), "b1", T0)
    assert err.value.code == "locked"
    with pytest.raises(RequestError) as err:
        rules.pick(view, ctx.fold(), "zz", T0)
    assert err.value.code == "unknown_card"
    taught(ctx, "car", "a1", T0)
    assert rules.pick(view, ctx.fold(), None, T0) == "a2"
    assert rules.pick(view, ctx.fold(), "a1", T0) == "a1"  # re-teach: allowed
    taught(ctx, "car", "a2", T0 + 1, 1)
    with pytest.raises(RequestError) as err:
        rules.pick(view, ctx.fold(), None, T0)
    assert err.value.code == "no_card_left"


def test_pick_skips_flagged_and_suspended(tmp_path: Path) -> None:
    ctx, plan, found = _setup(tmp_path)
    found["a1"].suspended = True
    view = rules.View("car", plan, found)
    with pytest.raises(RequestError):
        rules.pick(view, ctx.fold(), None, T0)  # a2 needs a1
    found["a1"].suspended = False
    ctx.log.append(
        [
            {
                "dev": "p",
                "eid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                "k": "flag",
                "s": "car",
                "c": "a1",
                "at": T0,
                "rev": 1,
            }
        ]
    )
    with pytest.raises(RequestError):
        rules.pick(view, ctx.fold(), None, T0)


def test_daily_cap_counts_new_cards_on_the_local_day(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    many = {f"c{i}": card("a", i) for i in range(12)}
    subject(ctx, found=many)
    view = _view(ctx)
    for i in range(10):
        taught(ctx, "car", f"c{i}", T0 + i, i)
    taught(ctx, "car", "c0", T0 + 20, 99)  # re-teach: not new
    assert rules.new_today(ctx.fold(), T0 + 100) == 10
    with pytest.raises(RequestError) as err:
        rules.pick(view, ctx.fold(), None, T0 + 100)
    assert err.value.code == "daily_new_cap"
    assert rules.pick(view, ctx.fold(), "c3", T0 + 100) == "c3"
    assert rules.pick(view, ctx.fold(), None, T0 + 2 * D) == "c10"
