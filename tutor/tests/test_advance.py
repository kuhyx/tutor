# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""fold_and_advance, pending, stats, the handler registry and the context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.credit import target_minutes
from tutor.curriculum import handlers
from tutor.curriculum.advance import fold_and_advance, pending
from tutor.curriculum.context import Context, wall_ms
from tutor.curriculum.stats import stats
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import T0, D, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path


def test_fold_and_advance_masters_unlocks_and_completes(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(
        ctx,
        modules=[module("a", status="ready"), module("b", "a"), module("c", "a")],
        found={"a1": card("a", 1)},
    )
    subject(ctx, "draft-one", plan_status="draft", status="draft")
    assert fold_and_advance(ctx) == {"changed": [], "generate": []}
    taught(ctx, "car", "a1", T0)
    review(ctx, "car", "a1", T0 + D, 3)
    assert fold_and_advance(ctx) == {
        "changed": ["car"],
        "generate": [["car", "b"], ["car", "c"]],
    }
    assert pending(ctx) == [("car", "b"), ("car", "c")]
    plan = ctx.subjects.plan("car")
    assert plan is not None
    for m in plan.modules:
        m.status = "ready" if m.id != "a" else "mastered"
    ctx.subjects.commit(
        "car",
        ctx.subjects.need_meta("car"),
        Change(plan=plan),
    )
    assert fold_and_advance(ctx)["changed"] == []  # b, c have no cards: recall 0
    for m in plan.modules:
        m.status = "mastered"
    ctx.subjects.commit(
        "car",
        ctx.subjects.need_meta("car"),
        Change(plan=plan),
    )
    assert fold_and_advance(ctx)["changed"] == ["car"]
    assert ctx.subjects.need_meta("car").status == "completed"


def test_stats_counts_days(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path)
    subject(ctx, found={"a1": card("a", 1)})
    taught(ctx, "car", "a1", T0)
    review(ctx, "car", "a1", T0 + D, 3)
    fakes.now[0] = T0 + D
    out = stats(ctx, minutes={"2000-01-01": 5})
    today = out["today"]
    want = target_minutes((T0 + D) / 1000)  # the day's weekday quota
    assert (today["new"], today["new_cap"], today["target"]) == (0, 25, want)
    assert today["credited_minutes"] == 0
    assert out["days"]["2000-01-01"] == {"minutes": 5, "taught": 0, "reviews": 0}
    assert sum(d["taught"] for d in out["days"].values()) == 1
    assert out["days"][today["day"]]["reviews"] == 1
    assert stats(ctx)["today"]["credited_minutes"] == 0  # no ledger in tests


def test_registry_and_context_defaults(tmp_path: Path) -> None:
    assert set(handlers.BUILD_HANDLERS) == {
        "subject_new",
        "plan_revise",
        "plan_edit",
        "plan_approve",
        "subject_finish",
        "module_pregenerate",
        "card_edit",
        "card_restore",
        "card_remove",
    }
    ctx = Context(tmp_path)
    assert ctx.device == (tmp_path / "device_id").read_text(encoding="utf-8").strip()
    assert abs(ctx.clock() - wall_ms()) < 5000
    assert ctx.fold().cards == {}
