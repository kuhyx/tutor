# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A redraft never closes a ``requires`` cycle through another module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import cardgen
from tutor.curriculum.redraft import drain, run
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._redraft import TEXT, URL, Fable, draft

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search in tests")


def test_a_requirement_on_a_card_that_waits_on_the_unit_is_dropped(
    tmp_path: Path,
) -> None:
    # Live 2026-11-21 (dry run): automation's fund-five-languages requires a
    # card of the later module ``languages``; its redraft required it back.
    ctx, fakes = make_ctx(tmp_path)
    fakes.texts[URL] = TEXT
    found = {
        "early": card("a", 1, "mid", source=URL),
        "mid": card("a", 2, "late", source=URL),
        "free": card("a", 3, source=URL),
        "late": card("b", 1, source=URL),
    }
    subject(ctx, modules=[module("a", status="ready"), module("b", "a")], found=found)
    new = [draft("piston", requires=["early", "free"]), draft("crank")]
    ctx.draft = Fable(new, pairs=[("piston", "late")])
    assert [u.name for u in run.start(ctx, only=frozenset({"car/b"}))] == ["car/b"]
    assert [u.state for u in drain.drain(ctx)] == [run.DONE]
    cards = ctx.subjects.cards("car")
    assert (cards["late"].rev, cards["late"].requires) == (2, ["free"])
    assert cards["early"].requires == ["mid"]


def test_a_bad_model_answer_is_asked_again_and_the_rest_replays(
    tmp_path: Path,
) -> None:
    ctx, fakes = make_ctx(tmp_path)
    fakes.texts[URL] = TEXT
    found = {f"old-{i}": card("a", i + 1, source=URL) for i in range(14)}
    subject(ctx, modules=[module("a", status="ready"), module("b", "a")], found=found)
    ids = [f"n{i}" for i in range(14)]
    fable = Fable([draft(i) for i in ids])  # no pieces: the cut covers nothing
    ctx.draft = fable
    run.start(ctx)
    (ended,) = drain.drain(ctx)
    assert (ended.state, ended.tries) == (run.PENDING, 1)
    assert "does not cover" in ended.error
    fable.pieces = [
        {"title": "One", "summary": "", "cards": ids[:7]},
        {"title": "Two", "summary": "", "cards": ids[7:]},
    ]
    (again,) = drain.drain(ctx)
    assert (again.state, again.tries) == (run.DONE, 2)
    # Only the bad answer was forgotten: the draft replayed from the cache.
    assert (fable.seen.count("split"), fable.seen.count("draft")) == (2, 1)


def test_two_backups_in_one_second_do_not_collide(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    subject(ctx, modules=[module("a", status="ready")], found={"x": card("a", 1)})
    first, second = run.backup(ctx, 5.0), run.backup(ctx, 5.0)
    assert second.name == f"{first.name}-2"
    assert (second / "car" / "cards.json").is_file()
