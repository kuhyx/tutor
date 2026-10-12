# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor regenerate``: gate a module's cards, suspend, regenerate."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import __main__ as tutor_main
from tutor.curriculum import cardgen, judge, regen
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

TOY = "https://en.wikibooks.org/wiki/How_To_Build_a_Pinewood_Derby_Car/Rules"


@pytest.fixture
def car(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path / "data")
    found = {
        "good": card("a", 1),
        "toy": card("a", 2, source=TOY),
        "old": card("a", 3, suspended=True),
        "other": card("b", 1),
    }
    subject(ctx, modules=[module("a", status="ready"), module("b", "a")], found=found)
    return ctx, fakes


def _verdicts(**on: bool) -> dict[str, Any]:
    return {
        "verdicts": [
            {"id": i, "on_topic": v, "module": "a", "reason": "r"}
            for i, v in on.items()
        ]
    }


def test_regenerate_suspends_refused_and_reopens(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    fakes.replies.append(_verdicts(good=True, toy=False))
    out = regen.regenerate(ctx, "car", "a")
    assert out == {
        "suspended": ["toy"],
        "why": ["toy: off topic (r)"],
        "kept": ["good"],
        "taught": [],
    }
    cards = ctx.subjects.cards("car")
    assert cards["toy"].suspended
    assert not cards["good"].suspended
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert (plan.modules[0].status, plan.modules[0].cards) == ("generating", 1)
    prompt = fakes.prompts[0][1]
    assert '"source": "How To Build a Pinewood Derby Car/Rules"' in prompt
    assert '"old"' not in prompt
    assert '"other"' not in prompt


def test_taught_cards_are_never_gated_or_suspended(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    taught = worker_event("taught", ("car", "toy"), dev=ctx.device, at=5, session="s")
    ctx.log.append([taught])
    fakes.replies.append(_verdicts(good=False))
    out = regen.regenerate(ctx, "car", "a")
    assert (out["suspended"], out["taught"]) == (["good"], ["toy"])
    deck, judged = fakes.prompts[0][1].split("Cards:", 1)
    assert '"toy"' not in judged  # never gated, only a card not to repeat
    assert '"toy"' in deck.split("Already in the deck", 1)[1]
    cards = ctx.subjects.cards("car")
    assert not cards["toy"].suspended
    assert cards["good"].suspended


def test_refusals(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    with pytest.raises(RequestError, match="not a module of an approved plan"):
        regen.regenerate(ctx, "car", "zz")
    with pytest.raises(RequestError, match="is locked, not ready/mastered/failed"):
        regen.regenerate(ctx, "car", "b")


def test_module_vanishes_during_the_gate(
    car: tuple[Context, Fakes], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _ = car

    def gate(*_: object) -> Any:
        plan = ctx.subjects.plan("car")
        assert plan is not None
        plan.modules = [m for m in plan.modules if m.id != "a"]
        ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(plan=plan))
        return {}, []

    monkeypatch.setattr(judge, "gate", gate)
    with pytest.raises(RequestError, match="vanished"):
        regen.regenerate(ctx, "car", "a")


def test_cli(
    car: tuple[Context, Fakes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctx, fakes = car
    roots: list[Path] = []

    def make(root: Path) -> Context:
        roots.append(root)
        return ctx

    assert regen.main(["car", "zz"], make) == 2
    assert "refused: car/zz is not a module" in capsys.readouterr().out
    fakes.replies.append(_verdicts(good=True, toy=True))
    assert regen.main(["car", "a", "--data", str(ctx.data_dir)], make) == 0
    assert json.loads(capsys.readouterr().out)["suspended"] == []
    assert roots[-1] == ctx.data_dir
    _ready(ctx)
    monkeypatch.setattr(cardgen, "generate", lambda *_: {"status": "ready"})
    fakes.replies.append(_verdicts(good=True, toy=True))
    assert regen.main(["car", "a", "--now"], make) == 0
    assert json.loads(capsys.readouterr().out)["generate"] == {"status": "ready"}


def _ready(ctx: Context) -> None:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    plan.modules[0].status = "ready"
    ctx.subjects.commit("car", ctx.subjects.need_meta("car"), Change(plan=plan))


def test_main_dispatches_regenerate(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        seen.append(argv)
        return 0

    monkeypatch.setattr(regen, "main", fake_main)
    assert tutor_main.main(["regenerate", "car", "a"]) == 0
    assert seen == [["car", "a"]]
