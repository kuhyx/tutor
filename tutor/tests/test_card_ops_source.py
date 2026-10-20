# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's edit moving a card to a page its research found.

The excerpt is re-quoted from the new page by code and checked against the
new URL by ``card_edit``; a page that does not support the card is refused.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from tutor import edit_flow, sources
from tutor.card_requests import CardEdit
from tutor.curriculum import card_ops
from tutor.tests.test_card_ops import BACK, FRONT, PISTON, car_subject, refused

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes


@pytest.fixture
def car(tmp_path: Path) -> tuple[Context, Fakes]:
    return car_subject(tmp_path)


def test_rewrite_can_move_a_card_to_a_page_research_found(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    rec = card_ops.rewrite(
        ctx, "car", "a1", card_ops.Rewrite(front=FRONT, back=BACK, source=f" {PISTON} ")
    )
    assert rec == ctx.subjects.cards("car")["a1"]
    assert (rec.front, rec.back, rec.source) == (FRONT, BACK, PISTON)
    assert rec.excerpt == (  # quoted by code from the new page, never by the model
        "It slides up and down inside the cylinder, pushed by the expanding gas "
        "of the burning fuel."
    )
    assert (rec.rev, rec.origin) == (2, "edited")


def test_a_source_swap_alone_keeps_the_text(car: tuple[Context, Fakes]) -> None:
    ctx, fakes = car
    fakes.texts[PISTON] = "Trivia. A thing is an object that one need not name."
    old = ctx.subjects.cards("car")["a1"]
    rec = card_ops.rewrite(
        ctx,
        "car",
        "a1",
        card_ops.Rewrite(front="", back="", source=PISTON, quote="thing object name"),
    )
    assert (rec.front, rec.back) == (old.front, old.back)
    assert (rec.source, rec.excerpt) == (
        PISTON,
        "A thing is an object that one need not name.",
    )


def test_a_source_swap_is_refused_when_the_page_does_not_support_it(
    car: tuple[Context, Fakes],
) -> None:
    ctx, fakes = car
    fakes.texts[PISTON] = "Cats and dogs are popular pets in many households."
    old = ctx.subjects.cards("car")["a1"]
    err = refused(
        lambda: card_ops.rewrite(
            ctx, "car", "a1", card_ops.Rewrite(front=FRONT, back=BACK, source=PISTON)
        )
    )
    assert "no sentence" in err.message
    assert ctx.subjects.cards("car")["a1"] == old  # nothing written


def test_a_source_swap_is_checked_against_the_new_url(
    car: tuple[Context, Fakes],
) -> None:
    ctx, fakes = car
    seen: list[tuple[str, str]] = []

    def check(cid: str, url: str, excerpt: str) -> sources.Mismatch | None:
        seen.append((url, excerpt))
        return fakes.check(cid, url, excerpt)

    swapped = dataclasses.replace(ctx, check=check)
    card_ops.rewrite(
        swapped, "car", "a1", card_ops.Rewrite(front=FRONT, back=BACK, source=PISTON)
    )
    assert [url for url, _ in seen] == [PISTON]
    fakes.bad_excerpts.add(seen[0][1])
    err = refused(
        lambda: card_ops.rewrite(
            swapped,
            "car",
            "a2",
            card_ops.Rewrite(front=FRONT + " Why?", back=BACK, source=PISTON),
        )
    )
    assert f"excerpt check failed for {PISTON}" in err.message


def test_a_source_swap_needs_an_https_page(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    err = refused(
        lambda: card_ops.rewrite(
            ctx, "car", "a1", card_ops.Rewrite(front="", back="", source="ftp:x")
        )
    )
    assert "https" in err.message


def test_the_same_source_is_no_swap(car: tuple[Context, Fakes]) -> None:
    ctx, _ = car
    old = ctx.subjects.cards("car")["a1"]
    rec = card_ops.rewrite(
        ctx,
        "car",
        "a1",
        card_ops.Rewrite(front="What is thing one?", back="", source=old.source),
    )
    assert (rec.source, rec.excerpt) == (old.source, old.excerpt)


def test_the_tutors_edit_op_carries_source_and_quote(
    car: tuple[Context, Fakes],
) -> None:
    ctx, _ = car
    edit = CardEdit("edit", card="a1", front=FRONT, back=BACK, source=PISTON)
    done = edit_flow.apply_edits(ctx, "car", "a1", (edit,))
    assert done.refusals == []
    assert done.notices == [f"Card updated: {FRONT}"]
    assert ctx.subjects.cards("car")["a1"].source == PISTON
