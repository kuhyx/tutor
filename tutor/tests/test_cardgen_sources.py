# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Card generation with the relevance steps: sources, the gate, regeneration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor import sources
from tutor.curriculum import cardgen, wiki
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests.test_cardgen import drafted

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

LONG = "pistons push cranks round " * 400
PAGES = [
    wiki.Page(wiki.WIKIPEDIA, "Car", LONG, exact=True),
    wiki.Page(wiki.WIKIPEDIA, "Engine", LONG, exact=True),
    wiki.Page(wiki.WIKIBOOKS, "Pinewood Derby Car/Rules", LONG, exact=False),
]


@pytest.fixture
def ctx_fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Context, Fakes]:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx, fakes = make_ctx(tmp_path / "data")
    subject(ctx, modules=[module("a", status="generating"), module("b", "a")])
    return ctx, fakes


def _verdicts(ids: list[str], off: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "verdicts": [
            {"id": i, "on_topic": i not in off, "module": "a", "reason": "r"}
            for i in ids
        ]
    }


def test_sources_pick_gate_and_settle(
    ctx_fakes: tuple[Context, Fakes], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = ctx_fakes
    asked: list[Any] = []

    def candidates(fetch: object, titles: list[str], queries: list[str]) -> list[Any]:
        asked.append((titles, queries))
        return PAGES

    monkeypatch.setattr(wiki, "candidates", candidates)
    reply = drafted(5)
    fakes.replies += [
        {"titles": ["Car", "Engine"]},
        {"keep": [1, 2], "why": ""},
        reply,
        _verdicts([f"card-{i}" for i in range(5)], off=("card-1",)),
    ]
    result = cardgen.generate(ctx, "car", "a")
    assert result == {"module": "a", "status": "ready", "cards": 4, "error": None}
    assert asked == [(["A", "Car", "Engine"], ["A", "A"])]
    pick = fakes.prompts[1][1]
    assert "Pinewood" not in pick  # the title fit dropped it before the model
    found = ctx.subjects.cards("car")
    assert [c for c in found if found[c].module == "a"] == [
        "card-0",
        "card-2",
        "card-3",
        "card-4",
    ]
    assert found["card-2"].requires == []  # card-1 was refused by the gate
    assert sources.page_text(found["card-0"].source) == LONG  # seeded
    assert '"B"' in fakes.prompts[2][1]  # other modules are named


def test_too_few_on_topic_sources(
    ctx_fakes: tuple[Context, Fakes], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = ctx_fakes
    monkeypatch.setattr(wiki, "candidates", lambda *_: PAGES)
    fakes.replies += [{"titles": []}, {"keep": [1], "why": ""}]
    error = cardgen.generate(ctx, "car", "a")["error"]
    assert error == "found 1 on-topic source(s) of 3, need 2"


def test_search_failure(
    ctx_fakes: tuple[Context, Fakes], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = ctx_fakes

    def offline(*_: object) -> list[Any]:
        msg = "network down"
        raise OSError(msg)

    monkeypatch.setattr(wiki, "candidates", offline)
    fakes.replies.append({"titles": []})
    error = cardgen.generate(ctx, "car", "a")["error"]
    assert error == "source search failed: network down"


def test_regeneration_appends_after_existing_cards(
    ctx_fakes: tuple[Context, Fakes], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes = ctx_fakes
    old = {
        "keep": card("a", 1),
        "gone": card(
            "a", 2, front="In a toy car race, what is banned?", suspended=True
        ),
        "x1": card("a", 3),
        "x2": card("a", 4),
    }
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(cards=old))
    monkeypatch.setattr(
        cardgen,
        "_sources",
        lambda *_: [wiki.Source("https://en.wikipedia.org/wiki/U", "U", "t")],
    )
    reply = drafted(3)
    reply["cards"][0]["source"] = 1
    reply["cards"][1]["source"] = 1
    reply["cards"][2]["source"] = 1
    reply["cards"][0]["requires"] = ["gone", "keep"]
    reply["cards"][0]["id"] = "gone"
    fakes.replies += [reply, _verdicts(["gone-2", "card-1", "card-2"])]
    cardgen.generate(ctx, "car", "a")
    found = ctx.subjects.cards("car")
    assert found["gone-2"].order == 5
    assert found["gone-2"].requires == ["keep"]
    assert [found[c].order for c in ("card-1", "card-2")] == [6, 7]
    assert (
        "Refused (off topic or another module's), do not repeat" in fakes.prompts[0][1]
    )
    assert '"gone"' not in fakes.prompts[0][1].split("Existing cards")[1].split("\n")[0]
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 6
    # A failed regeneration keeps a module that still has cards open.
    plan.modules[0].status = "generating"
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(plan=plan))
    fakes.replies += [drafted(1), _verdicts(["card-0"], off=("card-0",))]
    monkeypatch.setattr(
        cardgen,
        "_sources",
        lambda *_: [wiki.Source("https://en.wikipedia.org/wiki/U", "U", "t")],
    )
    result = cardgen.generate(ctx, "car", "a")
    assert (result["status"], result["cards"]) == ("ready", 6)
    assert "only 0 card(s) passed" in str(result["error"])
