# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""no_card_left: the subject title and the next step, never the slug."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import rules
from tutor.curriculum.errors import RequestError
from tutor.tests._cur import T0, H, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context


def _no_card(view: rules.View, ctx: Context, now: int) -> RequestError:
    with pytest.raises(RequestError) as err:
        rules.pick(view, ctx.fold(), None, now)
    assert err.value.code == "no_card_left"
    assert "slug" not in err.value.message
    assert err.value.message.startswith("Hosting WWW — ")
    return err.value


def test_no_card_left_names_the_title_and_the_next_step(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    found = {"a1": card("a", 1), "a2": card("a", 2), "b1": card("b", 1)}
    mods = [module("dns-slug", status="ready"), module("b", "dns-slug")]
    mods[0].title = "DNS i CNAME"
    found["a1"].module = found["a2"].module = "dns-slug"
    plan = subject(ctx, "hosting-slug", modules=mods, found=found)
    view = rules.View("hosting-slug", plan, found, title="Hosting WWW")
    for i, cid in enumerate(("a1", "a2")):
        taught(ctx, "hosting-slug", cid, T0 + i, i)
    err = _no_card(view, ctx, T0 + H)
    assert err.message == (
        "Hosting WWW — all cards of “DNS i CNAME” are taught. "
        "Review them to open the next module."
    )
    assert err.extra == {
        "subject_title": "Hosting WWW",
        "next": "review_module",
        "module": "dns-slug",
        "module_title": "DNS i CNAME",
    }
    assert err.result(5)["next"] == "review_module"
    review(ctx, "hosting-slug", "a1", T0 + H, 3)
    review(ctx, "hosting-slug", "a2", T0 + H + 1, 3)
    folded = ctx.fold()
    due = min(
        state["due"]
        for cid in ("a1", "a2")
        if (state := folded.card("hosting-slug", cid).fsrs_state())
    )
    mods[1].status = "generating"  # what advance_statuses did meanwhile
    err = _no_card(view, ctx, due)
    assert err.extra == {
        "subject_title": "Hosting WWW",
        "next": "reviews_due",
        "due_at": due,
    }
    assert "are due now" in err.message
    assert "still being written" in err.message
    assert "next review is due" in _no_card(view, ctx, due - 1).message


def test_no_card_left_with_nothing_taught_is_none(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    plan = subject(ctx, "hosting-slug", modules=[module("a", status="generating")])
    view = rules.View("hosting-slug", plan, {}, title="Hosting WWW")
    err = _no_card(view, ctx, T0)
    assert err.extra == {"subject_title": "Hosting WWW", "next": "none"}
    plan.modules[0].status = "locked"
    assert "no card is open" in _no_card(view, ctx, T0).message
    untitled = rules.View("hosting-slug", plan, {})
    with pytest.raises(RequestError) as caught:
        rules.pick(untitled, ctx.fold(), None, T0)
    assert caught.value.message.startswith("This subject — ")
