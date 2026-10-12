# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Just-in-time card generation: sources, model draft, verified cards only."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import card_rules, cardgen, draft_prompt, judge, wiki
from tutor.curriculum.errors import RequestError
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

SOURCES = [
    wiki.Source("https://en.wikipedia.org/wiki/A", "A", "text a"),
    wiki.Source("https://en.wikibooks.org/wiki/B", "B", "text b"),
]


def drafted(n: int, **over: Any) -> dict[str, Any]:
    """A model answer with ``n`` valid cards."""
    cards = [
        {
            "id": f"card-{i}",
            "front": f"What does part {i} do?",
            "back": "It turns.",
            "source": 1 + i % 2,
            "excerpt": f"part {i} turns the crank shaft round and round",
            "requires": [f"card-{i - 1}"] if i else [],
        }
        for i in range(n)
    ]
    for key, value in over.items():
        cards[0][key] = value
    return {"cards": cards}


@pytest.fixture
def gen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Context, Fakes, list[wiki.Source]]:
    ctx, fakes = make_ctx(tmp_path)
    found = list(SOURCES)
    monkeypatch.setattr(cardgen, "_sources", lambda *_: found)
    monkeypatch.setattr(judge, "gate", lambda _c, _m, _mod, cards, _t: (cards, []))
    subject(
        ctx,
        modules=[module("a", status="generating"), module("b", "a"), module("c", "b")],
        found={"old": card("z", 1)},
    )
    return ctx, fakes, found


def _module(ctx: Context, mid: str = "a") -> Any:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    return plan.module(mid)


def test_generate_keeps_verified_cards(
    gen: tuple[Context, Fakes, list[wiki.Source]],
) -> None:
    ctx, fakes, _ = gen
    reply = drafted(6)
    reply["cards"][1]["excerpt"] = "bad excerpt that is not on the page at all"
    reply["cards"][2]["front"] = "word " * 30
    reply["cards"][3]["source"] = 9
    reply["cards"] += ["junk"]
    fakes.bad_excerpts.add("bad excerpt that is not on the page at all")
    fakes.replies.append(reply)
    result = cardgen.generate(ctx, "car", "a")
    assert result == {"module": "a", "status": "ready", "cards": 3, "error": None}
    found = ctx.subjects.cards("car")
    assert [cid for cid in found if found[cid].module == "a"] == [
        "card-0",
        "card-4",
        "card-5",
    ]
    assert found["card-4"].requires == []  # card-3 was refused
    assert found["card-5"].requires == ["card-4"]
    assert found["card-4"].source == SOURCES[0].url
    assert found["card-5"].source == SOURCES[1].url
    assert [found[c].order for c in ("card-0", "card-4", "card-5")] == [1, 2, 3]
    system, prompt = fakes.prompts[0]
    assert system == draft_prompt.SYSTEM
    assert '<source n="2" url="https://en.wikibooks.org/wiki/B">' in prompt
    assert '"old"' in prompt


def test_too_few_cards_fails_the_module(
    gen: tuple[Context, Fakes, list[wiki.Source]],
) -> None:
    ctx, fakes, _ = gen
    fakes.replies.append(drafted(2))
    result = cardgen.generate(ctx, "car", "a")
    assert result["status"] == "failed"
    assert result["error"] == "only 2 card(s) passed the checks"
    assert _module(ctx).error == result["error"]
    assert cardgen.generate(ctx, "car", "a") == {"module": "a", "status": "failed"}


def test_model_failure_and_bad_answers(
    gen: tuple[Context, Fakes, list[wiki.Source]],
) -> None:
    ctx, fakes, _ = gen
    fakes.replies.append(RequestError("model_error", "the model is down"))
    assert cardgen.generate(ctx, "car", "a")["error"] == "the model is down"
    _reset(ctx)
    fakes.replies.append({"cards": "x"})
    assert cardgen.generate(ctx, "car", "a")["status"] == "failed"


def _reset(ctx: Context) -> None:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    plan.modules[0].status = "generating"
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(plan=plan))


def test_source_problem_fails_the_module(
    gen: tuple[Context, Fakes, list[wiki.Source]], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _, _ = gen
    monkeypatch.setattr(cardgen, "_sources", lambda *_: "found 1 on-topic source")
    result = cardgen.generate(ctx, "car", "a")
    assert (result["status"], result["error"]) == ("failed", "found 1 on-topic source")


def test_prefixed_module_ids(gen: tuple[Context, Fakes, list[wiki.Source]]) -> None:
    ctx, fakes, _ = gen
    plan = ctx.subjects.plan("car")
    assert plan is not None
    plan.modules[0].prefixes = ["eng-"]
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(plan=plan))
    reply = drafted(3)
    reply["cards"][1]["id"] = "eng-already"
    reply["cards"][2]["id"] = ""
    fakes.replies.append(reply)
    cardgen.generate(ctx, "car", "a")
    ids = [c for c, rec in ctx.subjects.cards("car").items() if rec.module == "a"]
    assert ids == ["eng-card-0", "eng-already", "eng-what-does-part-2-do"]


def test_not_generating_or_gone(
    gen: tuple[Context, Fakes, list[wiki.Source]], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes, _ = gen
    assert cardgen.generate(ctx, "car", "b") == {"module": "b", "status": "locked"}
    assert cardgen.generate(ctx, "car", "zz") == {"module": "zz", "status": None}
    # The plan changed under a running generation: nothing is written.
    fakes.replies.append(drafted(3))
    real = cardgen._outcome

    def racing(ctx_: Context, subj: str, mod: Any) -> Any:
        out = real(ctx_, subj, mod)
        _module_status(ctx_, "a", "locked")
        return out

    monkeypatch.setattr(cardgen, "_outcome", racing)
    assert cardgen.generate(ctx, "car", "a") == {"module": "a", "status": None}
    assert "card-0" not in ctx.subjects.cards("car")


def _module_status(ctx: Context, mid: str, status: str) -> None:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    target = plan.module(mid)
    assert target is not None
    target.status = status
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(plan=plan))


def test_card_rules_topic_without_prefixes() -> None:
    assert card_rules.topic(module("a")).prefixes == ("",)
    assert card_rules.as_card("x", card("a", 1), module("a")).topic.title == "A"
