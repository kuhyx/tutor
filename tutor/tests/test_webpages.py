# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pinned subjects: cards only from the web pages named in the goal."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor import sources
from tutor.curriculum import cardgen, judge, plan_ops, planner, webpages, wiki
from tutor.curriculum.errors import RequestError
from tutor.curriculum.records import Meta, Plan
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import T0, make_ctx, module
from tutor.tests.test_cardgen import drafted

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

PG = "https://paulgraham.com/taste.html"
DS = "https://paulgraham.com/ds.html"
GOAL = f"Product & design taste: {PG}, {DS}. And {PG} again"
ESSAY = "Taste for Makers \n \n February 2002 " + "good design is simple " * 400


def test_pinned_urls_in_order_once_without_punctuation() -> None:
    assert webpages.pinned(GOAL) == [PG, DS]
    assert webpages.pinned("how a car works") == []
    assert webpages.pinned("see (https://a.example/x).") == ["https://a.example/x"]


def test_title_is_the_first_line_else_the_url() -> None:
    assert webpages.title(ESSAY, PG) == "Taste for Makers"
    assert webpages.title("   ", "https://a.example/dir/essay.html") == "essay.html"
    assert webpages.title("", "https://a.example/") == "a.example"


def test_fetch_refuses_a_missing_or_short_page_by_name() -> None:
    texts = {PG: ESSAY, DS: "too short"}
    with pytest.raises(RequestError, match=r"ds\.html.*too little text"):
        webpages.fetch(texts.__getitem__, [PG, DS])

    def offline(url: str) -> str:
        msg = "network down"
        raise OSError(msg)

    with pytest.raises(RequestError, match=r"cannot fetch .*taste\.html"):
        webpages.fetch(offline, [PG])


def _pinned(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path / "data")
    fakes.texts = {PG: ESSAY, DS: ESSAY.replace("Taste for Makers", "Do Things")}
    plan = Plan(1, "approved", "n", [module("a", status="generating")])
    meta = Meta("Taste", GOAL, "active", T0)
    ctx.subjects.commit("taste", meta, Change(plan=plan, cards={}, concepts=[]))
    return ctx, fakes


def test_planner_is_told_the_pinned_pages(tmp_path: Path) -> None:
    ctx, fakes = _pinned(tmp_path)
    mods = [{"id": m, "title": m, "summary": "s", "requires": []} for m in "xyz"]
    fakes.replies.append(
        {"title": "Taste", "notes": "n", "profile": {}, "modules": mods}
    )
    planner.draft(ctx, GOAL, fixed=[])
    prompt = fakes.prompts[0][1]
    assert "ONLY from the pages below" in prompt
    assert f'title="Taste for Makers" url="{PG}"' in prompt
    assert f'title="Do Things" url="{DS}"' in prompt


def test_subject_new_fails_visibly_on_an_unreachable_page(tmp_path: Path) -> None:
    ctx, fakes = make_ctx(tmp_path / "data")
    with pytest.raises(RequestError, match="cannot fetch"):
        plan_ops.subject_new({"text": GOAL}, ctx)
    meta = ctx.subjects.need_meta(next(iter(ctx.subjects.subjects())))
    assert meta.status == "failed"
    assert "cannot fetch" in (meta.error or "")
    assert fakes.prompts == []  # no model call for a plan it cannot source


def test_cards_come_only_from_pinned_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx, fakes = _pinned(tmp_path)

    def no_wiki(*_: object) -> list[wiki.Page]:
        pytest.fail("a pinned subject must not search a wiki")

    monkeypatch.setattr(wiki, "candidates", no_wiki)
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    fakes.replies += [{"keep": [1], "why": ""}, drafted(6)]
    result = cardgen.generate(ctx, "taste", "a")
    assert result["status"] == "ready", result
    found = ctx.subjects.cards("taste")
    assert {c.source for c in found.values()} == {PG}
    assert "Do Things" in fakes.prompts[0][1]  # both pages were candidates


def test_no_pinned_page_fits_the_module(tmp_path: Path) -> None:
    ctx, fakes = _pinned(tmp_path)
    fakes.replies.append({"keep": [], "why": ""})
    error = cardgen.generate(ctx, "taste", "a")["error"]
    assert error == "none of the 2 pinned page(s) covers this module"


def test_subject_id_leaves_the_urls_out() -> None:
    goal = f"Product and design taste: {PG} {DS}"
    assert plan_ops.subject_id(goal, set()) == "product-and-design-taste"
    # Only a URL: its words still name the subject.
    assert plan_ops.subject_id(PG, set()).startswith("https-paulgraham-com")


def test_a_pinned_page_gone_at_card_time_fails_the_module(tmp_path: Path) -> None:
    ctx, fakes = _pinned(tmp_path)
    del fakes.texts[DS]
    error = cardgen.generate(ctx, "taste", "a")["error"]
    assert error == f"cannot fetch {DS}: no text for {DS}"
    assert fakes.prompts == []
