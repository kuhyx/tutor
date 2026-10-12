# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The plan requests: new subject, revise, edit, approve, finish."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import plan_ops
from tutor.curriculum.errors import RequestError
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests.test_planner import plan_reply

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes


def _code(call: Any, body: dict[str, Any], ctx: Context) -> str:
    with pytest.raises(RequestError) as err:
        call(body, ctx)
    return err.value.code


@pytest.fixture
def made(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies.append(plan_reply("engine", "brakes", "wheels"))
    assert plan_ops.subject_new({"text": "I want to learn how a car works"}, ctx) == {
        "subject": "how-a-car-works"
    }
    return ctx, fakes


def test_subject_id_strips_filler() -> None:
    assert (
        plan_ops.subject_id("Teach me about Rust lifetimes", set()) == "rust-lifetimes"
    )
    assert plan_ops.subject_id("I'd like to understand tides", {"tides"}) == "tides-2"


def test_subject_new_writes_a_draft(made: tuple[Context, Fakes]) -> None:
    ctx, _ = made
    meta = ctx.subjects.need_meta("how-a-car-works")
    plan = ctx.subjects.plan("how-a-car-works")
    assert (meta.status, meta.title, meta.plan_rev, meta.rev) == (
        "draft",
        "How a car works",
        1,
        2,
    )
    assert plan is not None
    assert (plan.rev, plan.status, [m.status for m in plan.modules]) == (
        1,
        "draft",
        ["locked"] * 3,
    )
    profile = ctx.subjects.profile_raw("how-a-car-works")
    assert profile is not None
    assert profile["domain"] == "cars"


def test_subject_new_failure_marks_failed_and_retry_reuses_id(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies = [RequestError("model_error", "down"), plan_reply("a", "b", "c")]
    assert _code(plan_ops.subject_new, {"text": "tides"}, ctx) == "model_error"
    meta = ctx.subjects.need_meta("tides")
    assert (meta.status, meta.error) == ("failed", "down")
    assert plan_ops.subject_new({"text": "tides"}, ctx) == {"subject": "tides"}
    assert ctx.subjects.need_meta("tides").rev == 4
    assert _code(plan_ops.subject_new, {"text": ""}, ctx) == "bad_request"


def test_revise_edit_conflicts(made: tuple[Context, Fakes]) -> None:
    ctx, fakes = made
    subj = "how-a-car-works"
    fakes.replies.append(plan_reply("x", "y", "z", notes=""))
    assert plan_ops.plan_revise(
        {"subject": subj, "plan_rev": 1, "comment": "less history"}, ctx
    ) == {"plan_rev": 2}
    plan = ctx.subjects.plan(subj)
    assert plan is not None
    assert [m.id for m in plan.modules] == ["x", "y", "z"]
    assert plan.history[0]["comment"] == "less history"
    assert plan.notes == "why"
    assert (
        _code(
            plan_ops.plan_revise, {"subject": subj, "plan_rev": 1, "comment": "c"}, ctx
        )
        == "plan_conflict"
    )
    mods = [
        {"id": "p", "title": "P"},
        {"id": "q", "title": "Q", "requires": ["p"]},
        {"id": "r", "title": "R", "status": "ready"},
    ]
    assert plan_ops.plan_edit(
        {"subject": subj, "plan_rev": 2, "modules": mods}, ctx
    ) == {"plan_rev": 3}
    plan = ctx.subjects.plan(subj)
    assert plan is not None
    assert [(m.id, m.status, m.depth) for m in plan.modules] == [
        ("p", "locked", 1),
        ("q", "locked", 1),
        ("r", "locked", 1),
    ]
    assert (
        _code(plan_ops.plan_edit, {"subject": subj, "plan_rev": 3, "modules": "x"}, ctx)
        == "bad_request"
    )
    assert (
        _code(
            plan_ops.plan_edit,
            {"subject": subj, "plan_rev": 3, "modules": mods[:2]},
            ctx,
        )
        == "bad_request"
    )
    assert (
        _code(plan_ops.plan_edit, {"subject": "Bad", "plan_rev": 3}, ctx)
        == "bad_request"
    )


def test_edit_cannot_drop_modules_with_cards(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(
        ctx,
        plan_status="draft",
        status="draft",
        modules=[module("a", status="ready", cards=2), module("b"), module("c")],
    )
    body: dict[str, Any] = {
        "subject": "car",
        "plan_rev": 1,
        "modules": [
            {"id": "b", "title": "B"},
            {"id": "c", "title": "C"},
            {"id": "d", "title": "D"},
        ],
    }
    assert _code(plan_ops.plan_edit, body, ctx) == "bad_request"
    body["modules"] = [{"id": "a", "title": "renamed"}, *body["modules"]]
    plan_ops.plan_edit(body, ctx)
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert (plan.modules[0].title, plan.modules[0].status, plan.modules[1].depth) == (
        "A",
        "ready",
        2,
    )


def test_approve_unlocks_roots_and_retries_failed(made: tuple[Context, Fakes]) -> None:
    ctx, _ = made
    subj = "how-a-car-works"
    assert (
        _code(plan_ops.plan_approve, {"subject": subj, "plan_rev": 9}, ctx)
        == "plan_conflict"
    )
    assert plan_ops.plan_approve({"subject": subj, "plan_rev": 1}, ctx) == {}
    plan = ctx.subjects.plan(subj)
    assert plan is not None
    assert (plan.status, [m.status for m in plan.modules]) == (
        "approved",
        ["generating", "locked", "locked"],
    )
    assert ctx.subjects.need_meta(subj).status == "active"
    assert (
        _code(
            plan_ops.plan_revise, {"subject": subj, "plan_rev": 1, "comment": "c"}, ctx
        )
        == "plan_conflict"
    )
    plan.modules[0].status = "failed"
    ctx.subjects.commit(subj, ctx.subjects.need_meta(subj), Change(plan=plan))
    plan_ops.plan_approve({"subject": subj, "plan_rev": 1}, ctx)
    again = ctx.subjects.plan(subj)
    assert again is not None
    assert again.modules[0].status == "generating"


def test_no_plan_is_a_conflict(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.replies.append(RequestError("model_error", "x"))
    with pytest.raises(RequestError):
        plan_ops.subject_new({"text": "tides"}, ctx)
    assert (
        _code(plan_ops.plan_approve, {"subject": "tides", "plan_rev": 0}, ctx)
        == "plan_conflict"
    )


def test_finish_review_only_and_go_deeper(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    mods = [module(m, status="mastered", cards=3) for m in ("a", "b", "c")]
    subject(ctx, modules=mods, found={"a1": card("a", 1)})
    body = {"subject": "car", "choice": "go_deeper"}
    assert _code(plan_ops.subject_finish, body, ctx) == "bad_request"  # not completed
    meta = ctx.subjects.need_meta("car")
    meta.status = "completed"
    ctx.subjects.commit("car", meta)
    assert _code(plan_ops.subject_finish, {**body, "choice": "x"}, ctx) == "bad_request"
    fakes.replies.append(plan_reply("d", "e", "f"))
    assert plan_ops.subject_finish(body, ctx) == {"plan_rev": 2}
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert [(m.id, m.depth) for m in plan.modules][2:] == [
        ("c", 1),
        ("d", 2),
        ("e", 2),
        ("f", 2),
    ]
    assert ctx.subjects.need_meta("car").status == "draft"
    assert "Go deeper" in fakes.prompts[0][1]
    meta = ctx.subjects.need_meta("car")
    meta.status = "completed"
    ctx.subjects.commit("car", meta)
    assert plan_ops.subject_finish({**body, "choice": "review_only"}, ctx) == {}
    assert ctx.subjects.need_meta("car").status == "review_only"
