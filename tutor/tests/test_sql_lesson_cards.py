# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Mastering a SQL lesson concept seeds its FSRS cards (never failing the turn)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import sql_cards
from tutor.curriculum.sql_bank import BANK
from tutor.curriculum.sql_card_spec import Outcome
from tutor.relay import sql_lesson_cards
from tutor.store import data_dir
from tutor.tests._cur import make_ctx, module, subject
from tutor.tests._sql_lesson_support import REAL, lesson, model, turn
from tutor.tests._sql_support import FakeSd, install_fake_fp, install_fake_sd

if TYPE_CHECKING:
    from tutor.curriculum.context import Context


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> str:
    """A running ``basics`` lesson (its first question asked); returns its id."""
    sd: FakeSd = install_fake_sd(monkeypatch)
    sd.run_result = dict(REAL)
    install_fake_fp(monkeypatch)
    model(monkeypatch, turn())
    return str(lesson()["lesson_id"])


def master(
    lid: str, monkeypatch: pytest.MonkeyPatch, **kw: object
) -> dict[str, object]:
    model(
        monkeypatch,
        turn(verdict="correct", mastered=True, summary_md="| a |", **kw),
    )
    return lesson(lesson_id=lid, answer="NULL is unknown, not false")


def sql_ctx() -> Context:
    ctx, _ = make_ctx(data_dir())
    subject(ctx, sql_cards.SUBJECT, modules=[module("a", status="ready")], found={})
    return ctx


def test_mastery_seeds_the_concepts_cards_taught_now(
    started: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = sql_ctx()
    monkeypatch.setattr(
        sql_lesson_cards,
        "run_query",
        lambda schema, query: Outcome(ok=True, rows=(("1",),)),
    )
    got = master(started, monkeypatch)
    assert got["summary_md"] == "| a |"
    ids = [s.card_id for s in BANK["NULL comparisons"]]
    assert list(ctx.subjects.cards(sql_cards.SUBJECT)) == ids
    state = ctx.fold().card(sql_cards.SUBJECT, ids[0])
    assert state.taught_at == ctx.clock()


def test_a_second_mastery_of_the_same_concept_adds_nothing(
    started: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = sql_ctx()
    monkeypatch.setattr(
        sql_lesson_cards,
        "run_query",
        lambda schema, query: Outcome(ok=True, rows=(("1",),)),
    )
    master(started, monkeypatch)
    before = (ctx.log.read(), ctx.subjects.cards(sql_cards.SUBJECT))
    lid2 = str(lesson()["lesson_id"]) if model(monkeypatch, turn()) else ""
    master(lid2, monkeypatch)
    assert before == (ctx.log.read(), ctx.subjects.cards(sql_cards.SUBJECT))


def test_no_mastery_no_cards(started: str, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = sql_ctx()
    model(monkeypatch, turn(verdict="correct", feedback_md="Yes."))
    lesson(lesson_id=started, answer="Ann and Bo")
    assert ctx.subjects.cards(sql_cards.SUBJECT) == {}


def test_a_seeding_failure_never_fails_the_turn(
    started: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def boom(*_: object, **__: object) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(sql_cards, "seed_concept", boom)
    got = master(started, monkeypatch)
    assert got["summary_md"] == "| a |"
    assert "disk full" in caplog.text
