# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Regression: the live "how a car works" module 1 that drifted off topic.

Replays a recorded real run (``scripts/record_cardgen_fixture.py``):
MediaWiki API answers and model replies, in call order. The subject started
with cards about a Pinewood Derby toy car (a Wikibooks hit for "Car") and car
history; the repair must suspend those and draft replacements from on-topic
sources only. Page texts in the fixture: Wikipedia / Wikibooks contributors,
CC BY-SA 4.0, clipped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tutor import sources
from tutor.curriculum import regen, relevance, wiki
from tutor.curriculum.eventlog import worker_event
from tutor.curriculum.records import CardRec, Meta, Plan
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import make_ctx

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

FIXTURE = Path(__file__).parent / "data" / "cardgen" / "car_overview.json"
PINEWOOD = "https://en.wikibooks.org/wiki/How_To_Build_a_Pinewood_Derby_Car/Rules"


def load(
    fixture: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Context, Fakes, dict[str, Any]]:
    """A context replaying ``fixture``: its pages, replies, subject, taught ids."""
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    monkeypatch.setenv("TUTOR_WIKI_CACHE", str(tmp_path / "wiki"))
    data = json.loads(fixture.read_text("utf-8"))
    ctx, fakes = make_ctx(tmp_path / "data")
    fakes.pages.update({u: json.dumps(b).encode() for u, b in data["fetch"].items()})
    fakes.replies.extend(r["reply"] for r in data["model"])
    before = data["before"]
    cards = {cid: CardRec.from_json(c) for cid, c in before["cards"].items()}
    plan = Plan.from_json(before["plan"])
    ctx.subjects.commit(
        data["subject"], Meta.from_json(before["meta"]), Change(plan=plan, cards=cards)
    )
    ctx.log.append(
        worker_event(
            "taught", (data["subject"], cid), dev=ctx.device, at=1, session="s"
        )
        for cid in before.get("taught", [])
    )
    return ctx, fakes, data


@pytest.fixture
def replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Context, Fakes, dict[str, Any]]:
    return load(FIXTURE, tmp_path, monkeypatch)


def test_pinewood_derby_cards_are_suspended_and_replaced(
    replay: tuple[Context, Fakes, dict[str, Any]],
) -> None:
    ctx, fakes, data = replay
    subject, module = data["subject"], data["module"]
    pinewood = [
        c for c, rec in ctx.subjects.cards(subject).items() if rec.source == PINEWOOD
    ]
    assert len(pinewood) == 4

    argv = [subject, module, "--data", str(ctx.data_dir), "--now"]
    assert regen.main(argv, lambda _root: ctx) == 0
    assert not fakes.replies  # every recorded call was made, in order

    cards = ctx.subjects.cards(subject)
    assert all(cards[c].suspended for c in pinewood)
    live = {
        c: rec for c, rec in cards.items() if rec.module == module and not rec.suspended
    }
    assert "what-is-car" in live  # on topic (and taught): kept
    assert PINEWOOD not in {rec.source for rec in live.values()}
    assert len(live) >= 6
    plan = ctx.subjects.plan(subject)
    assert plan is not None
    current = plan.module(module)
    assert current is not None
    assert (current.status, current.cards) == ("ready", len(live))
    orders = [rec.order for rec in live.values()]
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders)


def test_code_drops_the_pinewood_page_before_the_model_sees_it(
    replay: tuple[Context, Fakes, dict[str, Any]],
) -> None:
    ctx, fakes, data = replay
    subject, module = data["subject"], data["module"]
    regen.main([subject, module, "--now"], lambda _root: ctx)
    pick = next(p for s, p in fakes.prompts if s.startswith("You choose source"))
    assert "Pinewood" not in pick
    assert "Central African Republic" not in pick
    draft = next(p for s, p in fakes.prompts if s.startswith("You write flashcards"))
    assert "Pinewood" not in draft.split("Existing cards", 1)[1].split("<source", 1)[1]

    # The same decision, deterministic, straight from the recorded pages.
    meta = ctx.subjects.need_meta(subject)
    plan = ctx.subjects.plan(subject)
    assert plan is not None
    mod = plan.module(module)
    assert mod is not None
    pages = wiki.candidates(ctx.fetch, [], [mod.title])
    assert PINEWOOD in {p.url for p in pages}
    kept = relevance.shortlist(pages, relevance.focus(meta, mod))
    assert PINEWOOD not in {p.url for p in kept}
    assert (
        relevance.title_fit(
            "How To Build a Pinewood Derby Car/Rules", relevance.focus(meta, mod)
        )
        < relevance.MIN_TITLE_FIT
    )
