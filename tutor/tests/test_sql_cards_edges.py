# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""SQL cards: dedupe, races, failures, the engine adapter and the CLI."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from tutor.__main__ import main as tutor_main
from tutor.cards import CardError
from tutor.curriculum import card_rules, sql_cards, sql_cards_cli
from tutor.curriculum.sql_bank import BANK
from tutor.curriculum.sql_card_spec import Outcome
from tutor.curriculum.sql_engine import run_query
from tutor.curriculum.subject_store import LOCK
from tutor.tests._cur import T0, D, make_ctx, module, subject
from tutor.tests._sql_cards_support import NULLS, SUBJ, runner, sql_subject

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    import pytest


def test_a_second_seed_changes_nothing_and_never_retaughts(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    sql_cards.seed_concept(ctx, "NULL comparisons", runner)
    before = (ctx.log.read(), ctx.subjects.cards(SUBJ), ctx.subjects.meta(SUBJ))
    again = sql_cards.seed_concept(ctx, "NULL comparisons", runner)
    assert (again.added, again.taught, again.skipped) == ([], [], {})
    assert before == (ctx.log.read(), ctx.subjects.cards(SUBJ), ctx.subjects.meta(SUBJ))


def test_an_untaught_leftover_is_taught_but_a_suspended_card_is_left(
    tmp_path: Path,
) -> None:
    ctx, _ = sql_subject(tmp_path)
    sql_cards.seed_concept(ctx, "NULL comparisons", runner)
    cards = ctx.subjects.cards(SUBJ)
    cards["sql-null-eq"].suspended = True
    ctx.subjects.commit(
        SUBJ, ctx.subjects.need_meta(SUBJ), sql_cards.Change(cards=cards)
    )
    got = sql_cards.seed_concept(ctx, "NULL comparisons", runner)
    assert got.added == []
    assert got.taught == []
    assert ctx.subjects.cards(SUBJ)["sql-null-eq"].suspended


def test_a_bad_excerpt_or_engine_failure_skips_only_that_card(tmp_path: Path) -> None:
    ctx, fakes = sql_subject(tmp_path)
    fakes.bad_excerpts.add(NULLS[0].excerpt)

    def flaky(schema: str, query: str) -> Outcome:
        if query == NULLS[1].query:
            msg = "docker is down"
            raise RuntimeError(msg)
        return runner(schema, query)

    got = sql_cards.seed_concept(ctx, "NULL comparisons", flaky)
    assert set(got.skipped) == {NULLS[0].key, NULLS[1].key}
    assert "excerpt" in got.skipped[NULLS[0].key]
    assert "docker is down" in got.skipped[NULLS[1].key]
    assert got.added == [s.card_id for s in NULLS[2:]]
    fakes.bad_excerpts.clear()
    ok = sql_cards.seed_concept(ctx, "NULL comparisons", runner)  # retry later
    assert ok.added == [s.card_id for s in NULLS[:2]]


def test_unknown_concept_or_missing_subject_is_a_quiet_no_op(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    assert sql_cards.seed_concept(ctx, "NULL comparisons", runner).added == []
    ctx2, _ = sql_subject(tmp_path / "other")
    assert sql_cards.seed_concept(ctx2, "window frames", runner).added == []
    plan = ctx2.subjects.plan(SUBJ)
    assert plan is not None
    assert plan.module(sql_cards.MODULE) is None


def test_seed_all_covers_every_concept(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    got = sql_cards.seed_all(ctx, runner)
    assert len(got.added) == sum(len(v) for v in BANK.values())


def _held_elsewhere() -> bool:
    """Whether another thread can NOT take the subject lock right now."""
    import threading

    got: list[bool] = []

    def probe() -> None:
        won = LOCK.acquire(timeout=0.3)
        got.append(won)
        if won:
            LOCK.release()

    thread = threading.Thread(target=probe)
    thread.start()
    thread.join()
    return not got[0]


def test_the_engine_runs_outside_the_subject_lock(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    held: list[bool] = []

    def watching(schema: str, query: str) -> Outcome:
        held.append(_held_elsewhere())
        return runner(schema, query)

    sql_cards.seed_concept(ctx, "anti-join", watching)
    assert held == [False]


def test_an_unapproved_plan_gets_no_cards(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, SUBJ, modules=[module("a", status="ready")], plan_status="draft")
    got = sql_cards.seed_concept(ctx, "NULL comparisons", runner)
    assert (got.added, got.taught) == ([], [])


def test_a_card_added_meanwhile_is_kept_not_overwritten(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)

    def racing(schema: str, query: str) -> Outcome:
        if not ctx.subjects.cards(SUBJ):  # the lesson's seed wins the race
            sql_cards.seed_concept(ctx, "anti-join", runner)
        return runner(schema, query)

    got = sql_cards.seed_concept(ctx, "anti-join", racing)
    assert got.added == []
    assert list(ctx.subjects.cards(SUBJ)) == ["sql-anti-join"]


def test_a_vanished_subject_while_running_writes_nothing(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)

    def vanishing(schema: str, query: str) -> Outcome:
        (ctx.subjects.dir(SUBJ) / "meta.json").unlink()
        return runner(schema, query)

    got = sql_cards.seed_concept(ctx, "anti-join", vanishing)
    assert got.added == []


def test_all_cards_failing_commits_nothing(tmp_path: Path) -> None:
    ctx, _ = sql_subject(tmp_path)
    rev = ctx.subjects.need_meta(SUBJ).rev

    def broken(schema: str, query: str) -> Outcome:
        msg = "bad"
        raise ValueError(msg)

    got = sql_cards.seed_concept(ctx, "anti-join", broken)
    assert (got.added, got.taught, list(got.skipped)) == ([], [], ["anti-join"])
    assert ctx.subjects.need_meta(SUBJ).rev == rev


def test_a_deck_rule_failure_refuses_the_whole_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _ = sql_subject(tmp_path)

    def refuse(*_: object) -> None:
        msg = "front is over 25 words"
        raise CardError(msg)

    monkeypatch.setattr(card_rules, "check_set", refuse)
    got = sql_cards.seed_concept(ctx, "anti-join", runner)
    assert got.added == []
    assert "front is over" in got.skipped["*"]
    assert ctx.subjects.cards(SUBJ) == {}
    assert ctx.log.read() == []


def test_the_engine_adapter_returns_rows_or_the_mysql_error_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    seen: list[str] = []

    @contextmanager
    def sandbox(schema: str) -> Iterator[SimpleNamespace]:
        seen.append(schema)
        yield SimpleNamespace(
            execute=lambda sql: SimpleNamespace(
                ok="BAD" not in sql,
                rows=[["1", "NULL"]] if "BAD" not in sql else [],
                code=None if "BAD" not in sql else 1054,
            )
        )

    drills = SimpleNamespace(ensure_running=lambda: seen.append("up"))
    monkeypatch.setitem(sys.modules, "sql_drills", drills)
    monkeypatch.setitem(
        sys.modules, "sql_drills._sandbox", SimpleNamespace(sandbox=sandbox)
    )
    assert run_query("CREATE TABLE t (x INT);", "SELECT 1") == Outcome(
        ok=True, rows=(("1", "NULL"),)
    )
    assert run_query("", "BAD") == Outcome(ok=False, code=1054)
    assert seen == ["up", "CREATE TABLE t (x INT);", "up", "SELECT 1;"]


def test_the_cli_backfills_every_concept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = sql_subject(tmp_path)
    monkeypatch.setattr(sql_cards_cli, "run_query", runner)
    monkeypatch.setattr(sql_cards_cli, "Context", lambda _root: ctx)
    assert sql_cards_cli.main(["--data", str(tmp_path), "--taught-days-ago", "3"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out["added"]) == 25
    assert out["skipped"] == {}
    taught = [e["at"] for e in ctx.log.read() if e["k"] == "taught"]
    assert set(taught) == {T0 - 3 * D}


def test_the_cli_exits_1_when_a_card_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _ = sql_subject(tmp_path)

    def down(schema: str, query: str) -> Outcome:
        msg = "docker is down"
        raise RuntimeError(msg)

    monkeypatch.setattr(sql_cards_cli, "run_query", down)
    monkeypatch.setattr(sql_cards_cli, "Context", lambda _root: ctx)
    assert sql_cards_cli.main([]) == 1
    assert (
        len(json.loads(capsys.readouterr().out)["skipped"]) == 23
    )  # the 2 rule-only cards need no engine


def test_python_m_tutor_dispatches_sql_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sql_cards_cli, "main", lambda argv: 7 if argv == ["--x"] else 1)
    assert tutor_main(["sql-cards", "--x"]) == 7
