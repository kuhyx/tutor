# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``card_edit``: deck rules, excerpt check, rev bump, ids never renamed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum.card_edit import card_edit
from tutor.curriculum.errors import RequestError
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.tests._cur import Fakes

GOOD: dict[str, Any] = {
    "subject": "car",
    "module": "a",
    "front": "What does a piston do?",
    "back": "It moves up and down.",
    "source": "https://en.wikipedia.org/wiki/Piston",
    "excerpt": "a piston is a moving part that slides in a cylinder",
    "requires": [],
}


@pytest.fixture
def edit(tmp_path: Path) -> tuple[Context, Fakes]:
    ctx, fakes = make_ctx(tmp_path)
    mods = [
        module("a", status="ready", cards=1, prefixes=["eng-"]),
        module("b", "a"),
        module("c"),
    ]
    subject(ctx, modules=mods, found={"eng-x": card("a", 1), "b-y": card("b", 1)})
    return ctx, fakes


def _refused(body: dict[str, Any], ctx: Context) -> RequestError:
    with pytest.raises(RequestError) as err:
        card_edit(body, ctx)
    return err.value


def test_edit_existing_bumps_rev(edit: tuple[Context, Fakes]) -> None:
    ctx, _ = edit
    assert card_edit({**GOOD, "card": "eng-x"}, ctx) == {"card": "eng-x", "rev": 2}
    rec = ctx.subjects.cards("car")["eng-x"]
    assert (rec.origin, rec.front, rec.order) == ("edited", GOOD["front"], 1)


def test_new_card_slug_prefix_and_count(edit: tuple[Context, Fakes]) -> None:
    ctx, _ = edit
    assert card_edit({**GOOD, "card": None, "requires": ["eng-x"]}, ctx) == {
        "card": "eng-what-does-a-piston-do",
        "rev": 1,
    }
    assert card_edit({**GOOD, "card": "eng-given"}, ctx)["card"] == "eng-given"
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.modules[0].cards == 3
    assert ctx.subjects.cards("car")["eng-given"].order == 3


@pytest.mark.parametrize(
    ("over", "code", "text"),
    [
        ({"card": "Bad"}, "bad_request", "must be ids"),
        ({"subject": "nope-subject"}, "bad_request", "unknown subject"),
        ({"front": 3}, "bad_request", "must all be strings"),
        ({"requires": "x"}, "bad_request", "list of ids"),
        ({"module": "zz"}, "edit_refused", "unknown module"),
        ({"card": "b-y"}, "edit_refused", "never move"),
        ({"card": "other-id"}, "edit_refused", "eng-"),
        ({"card": None, "back": "word " * 31}, "edit_refused", "over 30 words"),
        ({"card": None, "requires": ["ghost"]}, "edit_refused", "unknown card"),
        ({"card": "eng-x", "requires": ["eng-x"]}, "edit_refused", "require itself"),
    ],
)
def test_refusals(
    edit: tuple[Context, Fakes], over: dict[str, Any], code: str, text: str
) -> None:
    ctx, _ = edit
    err = _refused({**GOOD, "card": None, **over}, ctx)
    assert (err.code, text in err.message) == (code, True)


def test_excerpt_check_refuses(edit: tuple[Context, Fakes]) -> None:
    ctx, fakes = edit
    fakes.bad_excerpts.add(GOOD["excerpt"])
    err = _refused({**GOOD, "card": "eng-x"}, ctx)
    assert err.code == "edit_refused"
    assert "excerpt check failed" in err.message
    assert ctx.subjects.cards("car")["eng-x"].rev == 1


def test_cycle_refused(edit: tuple[Context, Fakes]) -> None:
    ctx, _ = edit
    card_edit({**GOOD, "card": "eng-n", "requires": ["eng-x"]}, ctx)
    err = _refused({**GOOD, "card": "eng-x", "requires": ["eng-n"]}, ctx)
    assert "cycle" in err.message


def test_no_plan(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path)
    from tutor.curriculum.records import Meta

    ctx.subjects.commit("car", Meta("C", "g", "drafting", 1))
    assert _refused({**GOOD, "card": None}, ctx).code == "edit_refused"
