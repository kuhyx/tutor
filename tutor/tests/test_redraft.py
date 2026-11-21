# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The backfill end to end: start, drain (build + swap), report."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import cardgen, paths
from tutor.curriculum.redraft import drain, report, run
from tutor.tests._redraft import Fable, car, draft

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search in tests")


def test_a_module_is_redrafted_and_swapped_in(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    ctx.log.append(
        [
            {
                "dev": "d1",
                "eid": "01M5KVMEPKMG4P62QYFA3BC6MH",
                "k": "flag",
                "at": 5,
                "s": "car",
                "c": "old-1",
                "rev": 1,
                "reason": "two questions in one card",
            }
        ]
    )
    fable = Fable(
        [draft("piston"), draft("crank"), draft("valve")],
        pairs=[("piston", "old-0"), ("crank", "old-1"), ("valve", "old-1")],
    )
    ctx.draft = fable
    found = run.start(ctx)
    assert [u.name for u in found] == ["car/a"]
    assert (tmp_path / "backups").is_dir()
    ended = drain.drain(ctx)
    assert [(u.state, u.tries) for u in ended] == [(run.DONE, 1)]
    assert fable.seen == ["draft", "judge", "gate", "match", "audit", "paths"]
    assert '"flag": ["two questions in one card"]' in fable.prompts["draft"]
    # The gate and the matcher read the flag too: a card a flag asks for is
    # never refused as off topic, and the flagged card's id goes to its fix.
    for kind in ("gate", "match"):
        assert '"flag": ["two questions in one card"]' in fable.prompts[kind], kind
    assert "being redrafted" in fable.prompts["gate"]
    cards = ctx.subjects.cards("car")
    live = {cid: c for cid, c in cards.items() if not c.suspended}
    assert sorted(live) == ["old-0", "old-1", "valve"]
    assert (live["old-0"].rev, live["old-0"].front) == (2, "What does the piston do?")
    assert (live["old-1"].rev, live["valve"].rev) == (2, 1)
    assert cards["old-2"].suspended
    assert "redraft" in cards["old-2"].tutor
    assert ctx.fold().card("car", "old-0").taught  # the schedule carried over
    assert not ctx.fold().card("car", "old-1").flagged(2)  # the rev bump cleared it
    path = paths.fresh(ctx, "car", "old-0") or {}
    assert path["opening"] == "What do you know about piston?"
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert (plan.modules[0].status, plan.modules[0].cards) == ("ready", 3)
    text = report.render(ctx)
    assert "1 of 1 modules redrafted; 0 not done." in text
    assert "- flag: two questions in one card" in text
    assert "- `old-2`: What is thing 3 of a?" in text
    assert "| `car` | 3 | 3 | 1 | 1 |" in text
    assert run.pending(ctx) == []
    assert drain.drain(ctx) == []


def test_a_big_module_is_cut_and_a_mastered_one_reopens(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path, n=14, status="mastered")
    meta = ctx.subjects.need_meta("car")
    meta.status = "completed"
    ctx.subjects.commit("car", meta)
    ids = [f"n{i}" for i in range(14)]
    cards = [draft(i) for i in ids]
    cards[13]["requires"] = ["n0", "n12", "old-0", "nope"]
    cards[1]["requires"] = ["n13"]  # a later card: could never open
    fable = Fable(
        cards,
        pairs=[("n13", "old-0")],
        pieces=[
            {"title": "Engine basics", "summary": "The parts.", "cards": ids[:7]},
            {"title": "Engine cycle", "summary": "The strokes.", "cards": ids[7:]},
        ],
    )
    ctx.draft = fable
    run.start(ctx)
    assert [u.state for u in drain.drain(ctx)] == [run.DONE]
    assert fable.seen.count("paths") == 2
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert [m.id for m in plan.modules] == ["a", "engine-cycle", "b", "c"]
    first, second, later = plan.modules[0], plan.modules[1], plan.modules[2]
    assert (first.title, first.status, first.cards) == ("Engine basics", "ready", 7)
    assert (second.requires, second.status) == (["a"], "ready")  # old-0 is taught
    assert later.requires == ["engine-cycle"]
    assert ctx.subjects.need_meta("car").status == "active"
    found = ctx.subjects.cards("car")
    assert found["old-0"].module == "engine-cycle"
    assert found["old-0"].requires == ["n0", "n12"]
    assert found["n1"].requires == []
    assert "- `car/a` -> a, engine-cycle" in report.render(ctx)


def test_a_piece_without_a_taught_card_waits_locked(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path, n=13)
    ids = [f"n{i}" for i in range(13)]
    fable = Fable(
        [draft(i) for i in ids],
        pairs=[("n0", "old-0")],
        pieces=[
            {"title": "One", "summary": "", "cards": ids[:7]},
            {"title": "Two", "summary": "", "cards": ids[7:]},
        ],
    )
    ctx.draft = fable
    run.start(ctx)
    drain.drain(ctx)
    plan = ctx.subjects.plan("car")
    assert plan is not None
    second = plan.modules[1]
    assert (second.id, second.status, second.pregenerated) == ("two", "locked", True)


def test_a_fully_matched_mastered_module_stays_mastered(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path, n=1, status="mastered")
    ctx.draft = Fable([draft("piston")], pairs=[("piston", "old-0")])
    run.start(ctx)
    drain.drain(ctx)
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].status == "mastered"


def test_no_passing_card_keeps_the_old_cards(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    fable = Fable([draft("piston", source=9)])
    ctx.draft = fable
    run.start(ctx)
    for tries in (1, 2, 3):
        ended = drain.drain(ctx)
        assert ended[0].tries == tries
    assert ended[0].state == run.FAILED
    assert "no card passed" in ended[0].error
    live = [c for c in ctx.subjects.cards("car").values() if not c.suspended]
    assert len(live) == 3
    assert "- `car/a` (failed): car/a: no card passed" in report.render(ctx)
