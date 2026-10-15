# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The model-free drill: picking, options, grading, review events and credit."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest

from tutor import credit, distractors, drill, unavailable
from tutor.curriculum.fold import fold
from tutor.curriculum.source import source_for
from tutor.store import Store
from tutor.tests._cur import T0, D, card, make_ctx, module, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

NOW = T0 / 1000 + 30 * 86_400  # a month after the cards were taught


def _setup(tmp_path: Path) -> tuple[drill.Drill, Context]:
    """Subject ``car``: a1, a2 taught (a2 due first); a3, b1 not taught."""
    ctx, _ = make_ctx(tmp_path)
    found = {
        "a1": card("a", 1, back="Answer one."),
        "a2": card("a", 2, back="Answer two."),
        "a3": card("a", 3, back="Answer three."),
        "b1": card("b", 1, back="Answer bee."),
    }
    subject(ctx, modules=[module("a", status="ready"), module("b")], found=found)
    taught(ctx, "car", "a1", T0 + D, 1)
    taught(ctx, "car", "a2", T0, 2)
    return drill.Drill(Store(tmp_path), ctx), ctx


def test_next_picks_the_oldest_due_taught_card(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    got = run.next(None, NOW)
    assert got["card"] == {
        "subject": "car",
        "id": "a2",
        "front": "What is thing 2 of a?",
    }
    assert "Answer two." in got["options"]
    assert "Answer bee." in got["options"]  # the topic has only 2 others
    assert len(got["options"]) == distractors.OPTIONS
    assert got["today"] == {"active_min": 0, "credited_min": 0}
    assert got["unavailable"] is None
    assert run.pending is not None
    assert run.pending.prompt_id == got["prompt_id"]


def test_answers_log_reviews_and_credit_like_the_tutor(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    first = run.next("car", NOW)
    prompt = run.pending
    assert prompt is not None
    got = run.answer(first["prompt_id"], prompt.answer, NOW + 45)
    assert got["correct"] is True
    assert got["back"] == "Answer two."
    assert got["excerpt"].startswith("a thing is")
    assert got["source"] == "https://en.wikipedia.org/wiki/Thing"
    assert got["minute_credited"] is False
    second = run.next("car", NOW + 50)
    assert second["card"]["id"] == "a1"  # a2 was reviewed Good: due later
    prompt = run.pending
    assert prompt is not None
    wrong = (prompt.answer + 1) % len(prompt.options)
    got = run.answer(second["prompt_id"], wrong, NOW + 80)
    assert got["correct"] is False
    assert got["answer_index"] == prompt.answer
    assert got["minute_credited"] is True
    assert got["today"] == {"active_min": 1, "credited_min": 1}
    reviews = [e for e in ctx.log.read() if e["k"] == "review"]
    assert [(e["c"], e["r"], e["dur_ms"], e["dev"]) for e in reviews] == [
        ("a2", drill.GOOD, 45_000, "dev-pc"),
        ("a1", drill.AGAIN, 30_000, "dev-pc"),
    ]
    assert fold(ctx.log.read()).card("car", "a2").reviews == [(reviews[0]["at"], 3)]
    rows = json.loads((tmp_path / "data/ledger.json").read_text())["entries"]
    assert run._run is not None
    assert [r["entry_id"] for r in rows] == [f"{run._run.session_id}-m1"]
    assert rows[0]["entry_id"].startswith("drill-")
    lines = (tmp_path / "drill").glob("drill-*.jsonl")
    kinds = [json.loads(x)["type"] for f in lines for x in f.read_text().splitlines()]
    assert kinds == ["prompt", "answer", "prompt", "credit", "answer"]


def test_a_quick_pick_and_a_replaced_prompt_earn_nothing(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    old = run.next(None, NOW)["prompt_id"]
    new = run.next(None, NOW + 100)["prompt_id"]
    with pytest.raises(drill.PromptGoneError, match="no longer open"):
        run.answer(old, 0, NOW + 101)
    got = run.answer(new, 0, NOW + 102)
    assert got["minute_credited"] is False
    assert run._today(NOW + 102)["active_min"] == 0
    with pytest.raises(drill.PromptGoneError):
        run.answer(new, 0, NOW + 103)  # answered already: never twice


def test_bad_choice_keeps_the_prompt_open(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    pid = run.next(None, NOW)["prompt_id"]
    with pytest.raises(ValueError, match="not one of the 4 options"):
        run.answer(pid, 4, NOW + 10)
    assert run.answer(pid, 0, NOW + 10)["answer_index"] in range(4)


def test_a_lost_prompt_after_restart_is_unknown(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    pid = run.next(None, NOW)["prompt_id"]
    fresh = drill.Drill(Store(tmp_path), ctx)
    with pytest.raises(drill.PromptGoneError) as err:
        fresh.answer(pid, 0, NOW + 10)
    assert err.value.code == "unknown_prompt"


def test_empty_when_nothing_is_taught(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, found={"a1": card("a", 1)})
    assert drill.Drill(Store(tmp_path), ctx).next("car", NOW) == {"empty": True}


def test_outage_window_and_new_run_each_day(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    unavailable.record("overloaded", NOW - 5, NOW + 600)
    got = run.next(None, NOW)
    assert got["unavailable"] == {"until": int(NOW + 600), "reason": "overloaded"}
    first = run._run
    assert first is not None
    tomorrow = credit.local_day(NOW)[2] + 60
    assert run._today(tomorrow)["active_min"] == 0
    run.next(None, tomorrow)
    assert run._run is not None
    assert run._run.session_id != first.session_id


def test_unmigrated_deck_uses_progress_and_rotates(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, _ = make_ctx(tmp_path)
    store = Store(tmp_path)
    deck = source_for(store, ctx, None).cards()
    first, second = deck[0].id, deck[1].id
    store.finish_card(second, "s1")
    store.finish_card(first, "s0")
    data = store.progress()
    data["cards_done"][second]["at"] = "not a time"
    store._save(data)
    run = drill.Drill(store, ctx)
    with caplog.at_level(logging.WARNING):
        got = run.next(None, NOW)
    assert got["card"]["id"] == second  # unreadable time: drilled as oldest
    assert "unreadable" in caplog.text
    run.answer(got["prompt_id"], 0, NOW + 10)
    assert run.next("automation", NOW + 20)["card"]["id"] == first  # rotated


def test_a_subject_without_a_plan_is_skipped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, plan_status="draft")
    (tmp_path / "subjects/car/plan.json").unlink()
    with caplog.at_level(logging.WARNING):
        got = drill.Drill(Store(tmp_path), ctx).next(None, NOW)
    assert "drill skips car" in caplog.text
    assert got == {"empty": True}  # the bare deck has nothing taught
