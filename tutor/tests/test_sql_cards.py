# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""SQL lesson cards: the bank, seeding a concept's cards, dedupe, due dates."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import sql_cards
from tutor.curriculum.sql_bank import BANK
from tutor.curriculum.sql_card_spec import CardSpec, Outcome, back_text, render
from tutor.relay.sql_lesson_plan import PLAN
from tutor.tests._cur import T0, D
from tutor.tests._sql_cards_support import NULLS, SUBJ, runner, sql_subject

if TYPE_CHECKING:
    from pathlib import Path


def test_bank_concepts_are_lesson_concepts_and_keys_are_unique() -> None:
    titles = {c.title for cs in PLAN.values() for c in cs}
    assert set(BANK) <= titles
    ids = [s.card_id for specs in BANK.values() for s in specs]
    assert len(ids) == len(set(ids)) >= 25


def test_every_spec_fits_the_card_budgets_and_is_https() -> None:
    for specs in BANK.values():
        for s in specs:
            assert len(s.front.split()) <= 25, s.key
            assert 6 <= len(s.excerpt.split()) <= 40, s.key
            assert s.source.startswith("https://"), s.key
            assert (not s.query) or s.query.split()[0].upper() in {"SELECT", "SET"}


def test_a_card_with_a_query_needs_an_engine_result() -> None:
    spec = CardSpec("k", "f", "R.", "https://x.y/z", "a b c d e f", "", "SELECT 1")
    with pytest.raises(ValueError, match="needs an engine result"):
        back_text(spec, None)


def test_render_rows_errors_and_empty() -> None:
    assert (
        render(Outcome(ok=True, rows=(("a", "1"), ("b", "NULL")))) == "(a,1) (b,NULL)."
    )
    assert render(Outcome(ok=True, rows=(("2",), ("NULL",)))) == "2, NULL."
    assert render(Outcome(ok=True)) == "No rows."
    assert render(Outcome(ok=False, code=1054)) == "ERROR 1054."


def test_back_is_the_real_result_then_the_rule() -> None:
    spec = CardSpec(
        "k", "f", "The rule.", "https://x.y/z", "a b c d e f", "", "SELECT 1"
    )
    assert back_text(spec, Outcome(ok=True, rows=(("1",),))) == "1. The rule."
    static = CardSpec("k", "f", "Just rule.", "https://x.y/z", "a b c d e f")
    assert back_text(static, None) == "Just rule."


def test_seeding_a_concept_adds_checked_cards_in_a_ready_module(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    got = sql_cards.seed_concept(ctx, "NULL comparisons", runner)
    assert got.added == [s.card_id for s in NULLS]
    assert not got.skipped
    plan = ctx.subjects.plan(SUBJ)
    assert plan is not None
    mod = plan.module(sql_cards.MODULE)
    assert mod is not None
    assert (mod.status, mod.cards, mod.requires) == ("ready", len(NULLS), [])
    rec = ctx.subjects.cards(SUBJ)["sql-null-eq"]
    assert rec.back.startswith("NULL, NULL. A comparison with NULL")
    assert rec.origin == "seed"
    assert rec.module == sql_cards.MODULE
    assert ctx.subjects.need_meta(SUBJ).rev > 1


def test_new_cards_are_taught_by_the_worker_at_the_given_time(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    got = sql_cards.seed_concept(ctx, "NULL comparisons", runner, taught_at=T0 - 9 * D)
    assert got.taught == got.added
    state = ctx.fold().card(SUBJ, "sql-null-eq")
    assert state.taught_at == T0 - 9 * D
    events = [e for e in ctx.log.read() if e["k"] == "taught"]
    assert {e["dev"] for e in events} == {ctx.device}


def test_backdated_cards_are_due_now_and_fresh_ones_are_not(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    sql_cards.seed_concept(ctx, "NULL comparisons", runner, taught_at=T0 - 9 * D)
    sql_cards.seed_concept(ctx, "anti-join", runner)  # taught now
    folded = ctx.fold()
    old, new = (folded.card(SUBJ, c).memory for c in ("sql-null-eq", "sql-anti-join"))
    assert old is not None
    assert new is not None
    assert old.due.timestamp() * 1000 <= T0 < new.due.timestamp() * 1000
