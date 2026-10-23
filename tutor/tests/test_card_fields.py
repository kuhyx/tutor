# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``mnemonic`` and ``split_of`` on curriculum cards (``DOCS-contract-struggle.md`` §1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from tutor.cards import Card, Topic
from tutor.curriculum import card_rules
from tutor.curriculum.card_edit import card_edit
from tutor.curriculum.errors import RequestError
from tutor.curriculum.records import CardRec
from tutor.prompt import system_prompt
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

AID = "Seal-in: the motor holds its own Start button."
BODY: dict[str, Any] = {
    "subject": "car",
    "card": "a1",
    "module": "a",
    "front": "What is thing 1 of a?",
    "back": "It is a thing.",
    "source": "https://en.wikipedia.org/wiki/Thing",
    "excerpt": "a thing is an object that one need not name",
    "requires": [],
}


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
    ctx, _ = make_ctx(tmp_path)
    found = {"a1": card("a", 1), "a2": card("a", 2, split_of="a9")}
    subject(ctx, modules=[module("a", status="ready", cards=2)], found=found)
    return ctx


def test_to_json_leaves_unset_fields_out() -> None:
    plain = card("a", 1).to_json()
    assert "mnemonic" not in plain
    assert "split_of" not in plain
    both = card("a", 1, mnemonic=AID, split_of="a0").to_json()
    assert (both["mnemonic"], both["split_of"]) == (AID, "a0")
    assert CardRec.from_json(both) == card("a", 1, mnemonic=AID, split_of="a0")


def test_as_card_carries_the_mnemonic() -> None:
    mod = module("a")
    assert card_rules.as_card("a1", card("a", 1, mnemonic=AID), mod).mnemonic == AID
    assert card_rules.as_card("a1", card("a", 1), mod).mnemonic == ""


def test_the_editor_sets_keeps_and_clears_the_mnemonic(ctx: Context) -> None:
    assert card_edit({**BODY, "mnemonic": f" {AID}\n "}, ctx)["rev"] == 2
    assert ctx.subjects.cards("car")["a1"].mnemonic == AID
    card_edit({**BODY, "front": "What is thing one of a?"}, ctx)  # absent: kept
    assert ctx.subjects.cards("car")["a1"].mnemonic == AID
    assert card_edit({**BODY, "mnemonic": ""}, ctx)["rev"] == 4
    assert ctx.subjects.cards("car")["a1"].mnemonic == ""


def test_a_new_card_may_carry_a_mnemonic(ctx: Context) -> None:
    got = card_edit({**BODY, "card": None, "front": "Why?", "mnemonic": AID}, ctx)
    assert ctx.subjects.cards("car")[got["card"]].mnemonic == AID


def test_a_long_or_non_string_mnemonic_is_refused(ctx: Context) -> None:
    with pytest.raises(RequestError) as err:
        card_edit({**BODY, "mnemonic": "w " * 41}, ctx)
    assert err.value.code == "edit_refused"
    assert "mnemonic is over 40 words" in err.value.message
    with pytest.raises(RequestError) as err:
        card_edit({**BODY, "mnemonic": 3}, ctx)
    assert err.value.code == "bad_request"
    assert ctx.subjects.cards("car")["a1"].rev == 1


def test_split_of_is_never_edited(ctx: Context) -> None:
    card_edit({**BODY, "card": "a2", "split_of": None, "front": "Thing 2?"}, ctx)
    assert ctx.subjects.cards("car")["a2"].split_of == "a9"
    card_edit({**BODY, "split_of": "a2"}, ctx)
    assert ctx.subjects.cards("car")["a1"].split_of == ""


def test_the_prompt_shows_a_mnemonic_only_when_set() -> None:
    topic = Topic("io", "Field I/O", ("io",))
    plain = Card("io-x", "Q?", "A.", "https://e.org/x", "ex cerpt", topic)
    assert "mnemonic" not in system_prompt(plain, [])
    aided = Card("io-x", "Q?", "A.", "https://e.org/x", "ex", topic, mnemonic=AID)
    assert f"\nmnemonic: {AID}\n" in system_prompt(aided, [])
