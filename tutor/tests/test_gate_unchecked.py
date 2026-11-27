# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The module gate names its unchecked cards (``gate_unchecked``, spec Q11).

A card read without Claude holds the gate until Claude checks it; a review
never passes it. The refusal lists those cards apart from ``gate_cards`` so
the app shows them as waiting for the check (mockup F5), not as a review.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tutor.curriculum import pick as picking
from tutor.curriculum import rules
from tutor.curriculum.errors import RequestError
from tutor.curriculum.eventlog import unchecked_event
from tutor.curriculum.no_card import Held, locked
from tutor.tests._cur import T0, H, card, make_ctx, module, review, subject, taught

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context


def _view(tmp_path: Path) -> tuple[Context, rules.View]:
    """Subject ``car``: module a (a1, a2) taught, module b (b1) untaught."""
    ctx, _ = make_ctx(tmp_path)
    found = {"a1": card("a", 1), "a2": card("a", 2), "b1": card("b", 1)}
    mods = [module("a", status="ready"), module("b", status="ready")]
    plan = subject(ctx, modules=mods, found=found)
    taught(ctx, "car", "a1", T0, 1)
    taught(ctx, "car", "a2", T0 + 1, 2)
    return ctx, rules.View("car", plan, found, title="Cars")


def _refused(ctx: Context, view: rules.View, card_id: str | None) -> RequestError:
    with pytest.raises(RequestError) as err:
        picking.pick(view, ctx.fold(), card_id, T0 + H + 9)
    return err.value


def _unchecked(ctx: Context, cid: str) -> None:
    ctx.log.append([unchecked_event(("car", cid), dev="dev-pc", at=T0 + 2)])


def test_a_reviewed_unchecked_card_is_named_apart(tmp_path: Path) -> None:
    ctx, view = _view(tmp_path)
    _unchecked(ctx, "a2")
    review(ctx, "car", "a1", T0 + H, 3)
    review(ctx, "car", "a2", T0 + H + 1, 3)
    err = _refused(ctx, view, None)
    assert (err.extra["gate_cards"], err.extra["gate_unchecked"]) == (["a2"], ["a2"])


def test_unreviewed_and_unchecked_cards_are_told_apart(tmp_path: Path) -> None:
    ctx, view = _view(tmp_path)
    _unchecked(ctx, "a2")
    err = _refused(ctx, view, None)
    assert err.extra["gate_cards"] == ["a1", "a2"]
    assert err.extra["gate_unchecked"] == ["a2"]


def test_no_unchecked_card_sends_an_empty_list(tmp_path: Path) -> None:
    ctx, view = _view(tmp_path)
    assert _refused(ctx, view, None).extra["gate_unchecked"] == []


def test_an_explicit_card_locked_by_the_gate_names_them_too(tmp_path: Path) -> None:
    ctx, view = _view(tmp_path)
    _unchecked(ctx, "a1")
    err = _refused(ctx, view, "b1")
    assert err.code == "locked"
    assert err.extra["gate_cards"] == ["a1", "a2"]
    assert err.extra["gate_unchecked"] == ["a1"]


def test_a_lock_with_no_gate_cards_has_no_unchecked_field() -> None:
    err = locked("Cars", "b1", subject="car", module=None, held=Held())
    assert "gate_unchecked" not in err.extra
