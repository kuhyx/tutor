# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Read mode: the next untaught card, its events in order, and the drill's pay."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import pytest

from tutor import credit, read_mode, unavailable
from tutor.curriculum import pick
from tutor.curriculum.errors import RequestError
from tutor.curriculum.source import SubjectSource, source_for
from tutor.drill import PromptGoneError
from tutor.store import Store
from tutor.tests._cur import T0, D, card, make_ctx, module, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

NOW = T0 / 1000 + 30 * 86_400  # a month after the first card was taught


def _setup(tmp_path: Path) -> tuple[read_mode.ReadMode, Context]:
    """``car``: a1 taught and never reviewed, so the gate shuts module b."""
    ctx, _ = make_ctx(tmp_path)
    found = {
        "a1": card("a", 1, back="Answer one."),
        "b1": card("b", 1, back="Answer bee."),
        "b2": card("b", 2, "b1", back="Answer bee two."),
        "b3": card("b", 3, back="Flagged one."),
    }
    modules = [module("a", status="ready"), module("b", status="ready")]
    subject(ctx, modules=modules, found=found)
    taught(ctx, "car", "a1", T0, 1)
    ctx.log.append(
        [
            {
                "dev": "d1",
                "eid": "01M4QSMFG0JGMMMBEPVFB6D1AC",
                "k": "flag",
                "s": "car",
                "c": "b3",
                "at": T0 + 5,
                "rev": 1,
            }
        ]
    )
    return read_mode.ReadMode(Store(tmp_path), ctx), ctx


def test_next_ignores_the_module_gate(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    with pytest.raises(RequestError):  # a Claude session would wait for a1
        source_for(Store(tmp_path), ctx, "car").pick(None)
    got = run.next(None, NOW)
    assert got["card"] == {
        "subject": "car",
        "id": "b1",
        "module": "b",
        "front": "What is thing 1 of b?",
        "back": "Answer bee.",
        "excerpt": "a thing is an object that one need not name",
        "source": "https://en.wikipedia.org/wiki/Thing",
    }
    assert got["today"] == {"active_min": 0, "credited_min": 0}
    assert got["unavailable"] is None
    assert run.pending is not None
    assert run.pending.prompt_id == got["prompt_id"]


def test_untaught_skips_held_flagged_and_skipped_cards(tmp_path: Path) -> None:
    _, ctx = _setup(tmp_path)
    view = SubjectSource(Store(tmp_path), ctx, "car").view()
    found = [cid for cid, _ in pick.untaught(view, ctx.fold())]
    assert found == ["b1"]  # b2 needs b1; b3 is flagged
    assert list(pick.untaught(view, ctx.fold(), skip="b1")) == []


def _events(ctx: Context, cid: str) -> list[tuple[str, int]]:
    return [(e["k"], e["at"]) for e in ctx.log.read() if e["c"] == cid]


def test_got_it_writes_taught_then_unchecked(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    pid = run.next("car", NOW)["prompt_id"]
    got = run.rate(pid, "got_it", NOW + 20)
    assert got == {
        "rated": "got_it",
        "minute_credited": False,
        "today": {"active_min": 0, "credited_min": 0},
    }
    assert _events(ctx, "b1") == [("taught", T0), ("unchecked", T0 + 1)]
    events = [e for e in ctx.log.read() if e["c"] == "b1"]
    assert {e["dev"] for e in events} == {"dev-pc"}
    assert events[0]["session"].startswith("read-")
    assert events[1]["src"] == "read"
    state = ctx.fold().card("car", "b1")
    assert state.taught
    assert state.unchecked
    fsrs = state.fsrs_state()
    assert fsrs is not None
    assert fsrs["due"] == T0 + 2 * D  # the contract's "read mode got it"
    assert Store(tmp_path).progress()["cards_done"]["b1"]["session"].startswith("read-")
    assert run.next("car", NOW + 30)["card"]["id"] == "b2"  # b1 taught: b2 opens


def test_again_adds_an_again_review_two_ms_after_taught(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    pid = run.next(None, NOW)["prompt_id"]
    assert run.rate(pid, "again", NOW + 20)["rated"] == "again"
    assert _events(ctx, "b1") == [
        ("taught", T0),
        ("unchecked", T0 + 1),
        ("review", T0 + 2),
    ]
    review = next(e for e in ctx.log.read() if e["k"] == "review")
    assert (review["r"], review["rev"], review["dur_ms"]) == (1, 1, 20_000)
    assert "src" not in review
    state = ctx.fold().card("car", "b1")
    assert state.unchecked
    fsrs = state.fsrs_state()
    assert fsrs is not None
    assert fsrs["due"] == T0 + 2 + D  # due in a day, not two


def test_a_rating_pays_like_the_drill(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    first = run.next(None, NOW)["prompt_id"]
    assert run.rate(first, "got_it", NOW + 45)["minute_credited"] is False
    ctx_now = ctx.clock
    second = run.next(None, NOW + 50)["prompt_id"]
    got = run.rate(second, "again", NOW + 80)
    assert ctx.clock is ctx_now  # the frozen clock never leaks into the context
    assert got["minute_credited"] is True
    assert got["today"] == {"active_min": 1, "credited_min": 1}
    rows = json.loads((tmp_path / "data/ledger.json").read_text())["entries"]
    assert len(rows) == 1
    row = rows[0]
    assert row["entry_id"].startswith("read-")
    assert row["kind"] == "credit"
    assert row["detail"]["subject"] == "car"
    assert row["detail"]["module"] == "b"
    assert "activity" not in row["detail"]  # a lesson minute, not a review
    lines = list((tmp_path / "read").glob("read-*.jsonl"))
    kinds = [json.loads(x)["type"] for f in lines for x in f.read_text().splitlines()]
    assert kinds == ["prompt", "rate", "prompt", "credit", "rate"]


def test_a_quick_rating_and_a_stale_prompt_earn_nothing(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    old = run.next(None, NOW)["prompt_id"]
    new = run.next(None, NOW + 100)["prompt_id"]
    with pytest.raises(PromptGoneError, match="no longer open"):
        run.rate(old, "got_it", NOW + 101)
    got = run.rate(new, "got_it", NOW + 102)
    assert got["minute_credited"] is False
    assert got["today"]["active_min"] == 0
    with pytest.raises(PromptGoneError) as err:
        run.rate(new, "got_it", NOW + 103)  # rated already: never twice
    assert err.value.code == "unknown_prompt"


def test_a_bad_rating_keeps_the_prompt_open(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    pid = run.next(None, NOW)["prompt_id"]
    with pytest.raises(ValueError, match="not a read rating"):
        run.rate(pid, "maybe", NOW + 10)
    assert run.rate(pid, "again", NOW + 10)["rated"] == "again"


def test_a_lost_prompt_after_restart_is_unknown(tmp_path: Path) -> None:
    run, ctx = _setup(tmp_path)
    pid = run.next(None, NOW)["prompt_id"]
    fresh = read_mode.ReadMode(Store(tmp_path), ctx)
    with pytest.raises(PromptGoneError):
        fresh.rate(pid, "got_it", NOW + 10)


def test_outage_window_and_a_new_run_each_day(tmp_path: Path) -> None:
    run, _ = _setup(tmp_path)
    unavailable.record("rate_limit", NOW - 5, NOW + 600)
    got = run.next(None, NOW)
    assert got["unavailable"] == {"until": int(NOW + 600), "reason": "rate_limit"}
    first = run.runs.current
    assert first is not None
    tomorrow = credit.local_day(NOW)[2] + 60
    run.next(None, tomorrow)
    assert run.runs.current is not None
    assert run.runs.current.session_id != first.session_id


def test_empty_when_nothing_is_left_to_read(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, found={"a1": card("a", 1)})
    taught(ctx, "car", "a1", T0)
    run = read_mode.ReadMode(Store(tmp_path), ctx)
    assert run.next("car", NOW) == {"empty": True}
    assert run.next(None, NOW) == {"empty": True}  # the bare deck is never read
    assert run.next("automation", NOW) == {"empty": True}
    assert run.pending is None


def test_an_archived_subject_is_never_read(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, found={"a1": card("a", 1)})
    ctx.log.append(
        [
            {
                "dev": "dev-pc",
                "eid": "01M4QSMFG0JGMMMBEPVFB6D1AD",
                "k": "subject_archive",
                "s": "car",
                "at": T0,
            }
        ]
    )
    assert read_mode.ReadMode(Store(tmp_path), ctx).next("car", NOW) == {"empty": True}


def test_a_subject_without_a_plan_is_skipped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, plan_status="draft")
    (tmp_path / "subjects/car/plan.json").unlink()
    subject(ctx, "van", found={"a1": card("a", 1)})
    with caplog.at_level(logging.WARNING):
        got = read_mode.ReadMode(Store(tmp_path), ctx).next(None, NOW)
    assert "read mode skips car" in caplog.text
    assert (got["card"]["subject"], got["card"]["id"]) == ("van", "a1")
