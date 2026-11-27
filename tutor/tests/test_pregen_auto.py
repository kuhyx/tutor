# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Automatic pre-drafting: the next locked module of a subject studied this week."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import archive, cardgen, handlers, judge, pregen, pregen_auto
from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.tests._cur import T0, D, card, make_ctx, module, review, subject, taught
from tutor.tests.test_pregen import SOURCES, drafted, mod

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

NOW = T0 + 30 * D


@pytest.fixture
def car(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Context, Fakes]:
    """``a`` ready with one card, ``b`` and ``c`` locked behind it."""
    ctx, fakes = make_ctx(tmp_path)
    monkeypatch.setattr(cardgen, "sources", lambda *_: list(SOURCES))
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    subject(
        ctx,
        modules=[
            module("a", status="ready", cards=1),
            module("b", "a"),
            module("c", "b"),
        ],
        found={"a-1": card("a", 1)},
    )
    return ctx, fakes


def test_an_active_subject_gets_its_next_locked_module_drafted_and_kept_locked(
    car: tuple[Context, Fakes],
) -> None:
    ctx, fakes = car
    review(ctx, "car", "a-1", NOW - 6 * D, 3)
    assert pregen_auto.queue(ctx, NOW) == [("car", "b")]
    assert (mod(ctx, "b").status, mod(ctx, "b").pregenerated) == ("generating", True)
    assert mod(ctx, "c").status == "locked"
    assert pregen_auto.queue(ctx, NOW) == []  # generating: never queued twice
    fakes.replies.append(drafted(3))
    got = handlers.generate(ctx, "car", "b")
    assert (got["status"], got["cards"]) == ("locked", 3)
    handlers.fold_and_advance(ctx)
    assert (mod(ctx, "b").status, mod(ctx, "b").pregenerated) == ("locked", True)
    assert pregen_auto.queue(ctx, NOW) == []  # one module in stock: c waits
    assert mod(ctx, "c").status == "locked"


def test_a_taught_event_counts_as_study(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    taught(ctx, "car", "a-1", NOW - D)
    assert pregen_auto.picks(ctx, NOW) == [("car", "b")]


def test_a_subject_idle_for_eight_days_gets_nothing(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    review(ctx, "car", "a-1", NOW - 8 * D, 3)
    assert pregen_auto.queue(ctx, NOW) == []
    assert mod(ctx, "b").status == "locked"


def test_an_archived_subject_is_skipped(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    review(ctx, "car", "a-1", NOW - D, 3)
    archive.subject_archive({"subject": "car"}, ctx)
    assert pregen_auto.picks(ctx, NOW) == []


def test_a_failed_pregeneration_is_not_followed_by_the_next_module(
    car: tuple[Context, Fakes],
) -> None:
    ctx, fakes = car
    review(ctx, "car", "a-1", NOW - D, 3)
    assert pregen_auto.queue(ctx, NOW) == [("car", "b")]
    fakes.replies.append({"cards": []})  # no card kept
    assert handlers.generate(ctx, "car", "b")["status"] == "failed"
    assert pregen_auto.queue(ctx, NOW) == []  # b drafts just in time on unlock


def test_only_the_first_locked_module_is_looked_at(
    tmp_path: Path,
) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(
        ctx,
        modules=[
            module("a", status="ready", cards=1),
            module("b", "a"),
            module("c", "b"),
        ],
        found={"a-1": card("a", 1), "b-1": card("b", 1)},
    )
    review(ctx, "car", "a-1", NOW - D, 3)
    assert pregen_auto.picks(ctx, NOW) == []  # b already has cards: in stock


def test_plans_without_a_locked_module_or_not_approved_are_skipped(
    tmp_path: Path,
) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, "done", modules=[module("a", status="ready")])
    subject(ctx, "draft", plan_status="draft")
    for n, name in enumerate(("done", "draft")):
        review(ctx, name, "x", NOW - D + n, 3)
    assert pregen_auto.picks(ctx, NOW) == []


def test_a_refused_queue_is_skipped_and_the_rest_go_on(
    car: tuple[Context, Fakes], monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _ = car
    subject(ctx, "bike")
    for n, name in enumerate(("bike", "car")):
        review(ctx, name, "a-1", NOW - D + n, 3)  # distinct eids
    real = pregen.module_pregenerate

    def flaky(body: dict[str, object], c: Context) -> dict[str, object]:
        if body["subject"] == "bike":
            msg = "changed meanwhile"
            raise RequestError(BAD_REQUEST, msg)
        return real(body, c)

    monkeypatch.setattr(pregen, "module_pregenerate", flaky)
    assert pregen_auto.queue(ctx, NOW) == [("car", "b")]
