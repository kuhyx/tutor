# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One redraft unit: its sources, the cut, the swap and its refusals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import cardgen, webpages, wiki
from tutor.curriculum.errors import BAD_REQUEST, MODEL_ERROR, RequestError
from tutor.curriculum.plan_context import Scope
from tutor.curriculum.redraft import gather, run, swap, unit
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._redraft import TEXT, URL, Fable, car, draft

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.curriculum.redraft.run import Before


@pytest.fixture(autouse=True)
def _no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search in tests")


def _snap(ctx: Context, fable: Fable) -> Before:
    ctx.model = ctx.draft = fable
    run.start(ctx)
    return run.before(ctx, "car")


def _big(n: int = 13) -> tuple[list[str], list[dict[str, Any]]]:
    ids = [f"n{i}" for i in range(n)]
    return ids, [draft(i) for i in ids]


@pytest.mark.parametrize("shape", ["short", "too_big", "untitled", "none", "empty"])
def test_a_cut_that_misses_a_card_is_refused(tmp_path: Path, shape: str) -> None:
    ctx, _ = car(tmp_path, n=14)
    ids, cards = _big()
    pieces = {
        "short": [{"title": "One", "summary": "", "cards": ids[:7]}],
        "too_big": [{"title": "One", "summary": "", "cards": ids}],
        "untitled": [
            {"title": "One", "summary": "", "cards": ids[:7]},
            {"title": "", "summary": "", "cards": ids[7:]},
        ],
        "none": [],
        "empty": [
            {"title": "One", "summary": "", "cards": ids},
            {"title": "Two", "summary": "", "cards": []},
        ],
    }[shape]
    snap = _snap(ctx, Fable(cards, pieces=pieces))
    with pytest.raises(RequestError, match="does not cover its 13 cards") as err:
        unit.build(ctx, snap, "a")
    assert err.value.code == MODEL_ERROR
    kept = ctx.subjects.cards("car")
    assert len(kept) == 14
    assert not any(c.suspended for c in kept.values())


def test_a_module_missing_from_the_snapshot_is_refused(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    snap = _snap(ctx, Fable([draft("piston")]))
    with pytest.raises(RequestError, match="car/zz is not in the snapshot"):
        unit.build(ctx, snap, "zz")


def test_a_module_without_a_readable_source_keeps_its_cards(tmp_path: Path) -> None:
    ctx, fakes = car(tmp_path)
    fable = Fable([draft("piston")])
    snap = _snap(ctx, fable)
    del fakes.texts[URL]  # the cited page cannot be read any more
    result = unit.build(ctx, snap, "a")
    assert (result.cards, result.sources) == ({}, [])
    assert result.dropped == ["no readable source for this module"]
    assert fable.seen == []  # no model call was spent
    with pytest.raises(RequestError, match="no card passed") as err:
        swap.apply(ctx, snap, result)
    assert "no readable source" in err.value.message
    assert len(ctx.subjects.cards("car")) == 3


def test_gather_reads_cited_pages_first_then_the_fresh_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = car(tmp_path)
    twice, once = "https://example.org/twice", "https://example.org/once"
    fakes.texts[twice] = "Twice cited\nbody " * 3
    fakes.texts[once] = "\n"  # no first line: the title is the URL's end
    old = {
        "p": card("a", 1, source=once),
        "q": card("a", 2, source=twice),
        "r": card("a", 3, source=twice),
        "s": card("a", 4, source="https://example.org/gone"),  # unreadable
    }
    news = wiki.Source(URL, "Engine", "fresh text")
    again = wiki.Source(twice, "Twice again", "same page")
    monkeypatch.setattr(cardgen, "sources", lambda *_: [again, news])
    plan = ctx.subjects.plan("car")
    assert plan is not None
    scope = Scope(
        ctx.subjects.need_meta("car"), plan.module("a") or plan.modules[0], plan
    )
    found = gather.gather(ctx, scope, old)
    assert [s.url for s in found] == [twice, once, URL]
    assert found[0].title == webpages.title(fakes.texts[twice], twice) == "Twice cited"
    assert found[1].title == "once"
    assert found[2] is news  # the fresh page the old cards never cited


@pytest.mark.parametrize("status", ["locked", "failed"])
def test_a_module_that_was_not_open_keeps_its_status(
    tmp_path: Path, status: str
) -> None:
    ctx, _ = car(tmp_path, status=status)
    snap = _snap(ctx, Fable([draft("piston")], pairs=[("piston", "old-0")]))
    swap.apply(ctx, snap, unit.build(ctx, snap, "a"))
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].status == status
    assert ctx.subjects.cards("car")["old-0"].rev == 2


def test_a_module_edited_after_the_snapshot_is_not_swapped(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    snap = _snap(ctx, Fable([draft("piston")], pairs=[("piston", "old-0")]))
    result = unit.build(ctx, snap, "a")
    cards = ctx.subjects.cards("car")
    cards["old-1"].rev += 1  # an edit landed while the unit was building
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(cards=cards))
    with pytest.raises(RequestError, match="changed since the snapshot") as err:
        swap.apply(ctx, snap, result)
    assert err.value.code == BAD_REQUEST
    assert ctx.subjects.cards("car")["old-0"].rev == 1
    assert not ctx.subjects.cards("car")["old-2"].suspended


def _two_modules(tmp_path: Path, found: dict[str, Any]) -> tuple[Context, Fable]:
    ctx, fakes = make_ctx(tmp_path)
    fakes.texts[URL] = TEXT
    mods = [module("a", status="ready"), module("b", "a", status="ready")]
    subject(ctx, modules=mods, found=found)
    fable = Fable([draft("piston", requires=["a1", "a5"])], pairs=[("piston", "b1")])
    ctx.model = ctx.draft = fable
    run.start(ctx, only=frozenset({"car/b"}))
    return ctx, fable


def _chain(**over: Any) -> dict[str, Any]:
    """Module ``a``: a diamond a1 -> (a2, a3) -> a4, and a5 that waits on ``b1``."""
    found = {
        "a1": card("a", 1, "a2", "a3", source=URL),
        "a2": card("a", 2, "a4", source=URL),
        "a3": card("a", 3, "a4", source=URL),
        "a4": card("a", 4, source=URL),
        "a5": card("a", 5, "b1", source=URL),
        "b1": card("b", 1, source=URL),
    }
    return {**found, **over}


def test_a_new_card_never_requires_a_card_that_waits_on_its_unit(
    tmp_path: Path,
) -> None:
    ctx, _ = _two_modules(tmp_path, _chain())
    snap = run.before(ctx, "car")
    swap.apply(ctx, snap, unit.build(ctx, snap, "b"))
    found = ctx.subjects.cards("car")
    assert found["b1"].rev == 2
    assert found["b1"].requires == ["a1"]  # a5 would have waited on b1 itself
    assert found["a5"].requires == ["b1"]


def test_a_subject_the_deck_rules_refuse_is_not_swapped(tmp_path: Path) -> None:
    ctx, _ = _two_modules(tmp_path, _chain(a4=card("a", 4, "ghost", source=URL)))
    snap = run.before(ctx, "car")
    result = unit.build(ctx, snap, "b")
    with pytest.raises(RequestError, match="ghost") as err:
        swap.apply(ctx, snap, result)
    assert err.value.code == BAD_REQUEST
    assert ctx.subjects.cards("car")["b1"].rev == 1
