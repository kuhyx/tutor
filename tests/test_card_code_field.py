# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A card's optional ``code`` (a skeleton): kept verbatim, capped, published.

The item's done check collects only ``tests/``, so these live here; the
sandbox fixture of ``tutor/tests`` is imported to keep HOME, the data dir,
the ledger key and the network out of reach.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import prompt
from tutor.cards import CardError, validate_card
from tutor.curriculum import card_rules, vet
from tutor.curriculum.card_edit import card_edit
from tutor.curriculum.errors import BAD_REQUEST, RequestError
from tutor.curriculum.records import MAX_CARD_BYTES, CardRec
from tutor.curriculum.wiki import Source
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import engine, wiring
from tutor.tests.conftest import tutor_sandbox

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

__all__ = ["tutor_sandbox"]  # autouse: HOME, data dir, key and network sandboxed

SKELETON = (
    "function twoSum(nums: number[], target: number): number[] {\n"
    "  const seen = new Map<number, number>();\n"
    "  for (let i = 0; i < nums.length; i++) {\n"
    "    // TODO: look up target - nums[i]\n"
    "  }\n"
    "  return [];\n"
    "}"
)
URL = "https://en.wikipedia.org/wiki/Piston"
EDIT: dict[str, Any] = {
    "subject": "car",
    "module": "a",
    "card": "a-x",
    "front": "What does a piston do?",
    "back": "It moves up and down.",
    "source": URL,
    "excerpt": "a piston is a moving part that slides in a cylinder",
    "requires": [],
}


def _bytes(rec: CardRec) -> int:
    """How big ``rec`` is, measured the way ``to_json`` caps it."""
    out = rec.to_json()
    return len(json.dumps(out, ensure_ascii=False).encode())


def _padded(base: CardRec, size: int) -> CardRec:
    """``base`` with a code field that brings the card to exactly ``size`` bytes."""
    rec = CardRec.from_json({**base.to_json(), "code": "x"})
    rec.code = "x" * (1 + size - _bytes(rec))
    return rec


def _ctx(tmp_path: Path, **kw: Any) -> Context:
    ctx, _ = make_ctx(tmp_path)
    mods = [module("a", status="ready", cards=1), module("b", "a"), module("c")]
    subject(ctx, modules=mods, found={"a-x": card("a", 1, source=URL, **kw)})
    return ctx


def test_card_code_field_round_trip_keeps_layout(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, code=SKELETON)
    raw = json.loads((ctx.subjects.dir("car") / "cards.json").read_text())
    assert raw["a-x"]["code"] == SKELETON
    assert ctx.subjects.cards("car")["a-x"].code == SKELETON


def test_card_code_field_absent_keeps_old_shape(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    raw = json.loads((ctx.subjects.dir("car") / "cards.json").read_text())
    assert "code" not in raw["a-x"]
    assert "code" not in card_rules.raw("a-x", ctx.subjects.cards("car")["a-x"])


def test_card_code_field_cap_refuses_oversized() -> None:
    base = card("a", 1)
    assert _bytes(_padded(base, MAX_CARD_BYTES)) == MAX_CARD_BYTES
    over = _padded(base, MAX_CARD_BYTES)
    over.code += "x"
    with pytest.raises(RequestError) as err:
        over.to_json()
    assert err.value.code == BAD_REQUEST


def test_card_code_field_newlines_count_against_the_cap() -> None:
    rec = _padded(card("a", 1), MAX_CARD_BYTES)
    rec.code = rec.code[:-2] + "\n"  # one character, two bytes once encoded
    assert _bytes(rec) == MAX_CARD_BYTES


def test_card_code_field_vet_keeps_layout_and_refuses_oversized(
    tmp_path: Path,
) -> None:
    ctx, _ = make_ctx(tmp_path)
    found = [
        Source(URL, "Piston", "a piston is a moving part that slides in a cylinder")
    ]
    item = {
        "id": "piston",
        "front": "What does a piston do?",
        "back": "It moves up and down.",
        "mnemonic": "",
        "source": 1,
        "excerpt": "a piston is a moving part that slides in a cylinder",
        "requires": [],
        "code": SKELETON + "   \n\n",
    }
    got = vet.one(ctx, module("a"), set(), found, item)
    assert not isinstance(got, str)
    assert got[1].code == SKELETON
    assert vet.as_item(got[0], got[1], found)["code"] == SKELETON
    big = vet.one(ctx, module("a"), set(), found, {**item, "code": "x" * 2000})
    assert big == f"card is over {MAX_CARD_BYTES} bytes"
    plain = vet.one(ctx, module("a"), set(), found, {**item, "code": None})
    assert not isinstance(plain, str)
    assert plain[1].code == ""


def test_card_code_field_edit_sets_keeps_and_clears(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    card_edit({**EDIT, "code": SKELETON + "  \n"}, ctx, judged=False)
    assert ctx.subjects.cards("car")["a-x"].code == SKELETON
    card_edit(EDIT, ctx, judged=False)  # absent: kept
    assert ctx.subjects.cards("car")["a-x"].code == SKELETON
    card_edit({**EDIT, "code": ""}, ctx, judged=False)
    assert ctx.subjects.cards("car")["a-x"].code == ""


def test_card_code_field_edit_refuses_oversized(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, code=SKELETON)
    with pytest.raises(RequestError) as err:
        card_edit({**EDIT, "code": "x" * 2000}, ctx, judged=False)
    assert err.value.code == BAD_REQUEST
    assert ctx.subjects.cards("car")["a-x"].code == SKELETON
    with pytest.raises(RequestError) as err:
        card_edit({**EDIT, "code": 7}, ctx, judged=False)
    assert err.value.code == BAD_REQUEST


def test_card_code_field_reaches_the_tutor_prompt(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, code=SKELETON)
    rec = ctx.subjects.cards("car")["a-x"]
    deck_card = card_rules.as_card("a-x", rec, module("a"))
    assert deck_card.code == SKELETON
    assert f"skeleton:\n{SKELETON}\n" in prompt.system_prompt(deck_card, [])
    plain = card_rules.as_card("a-x", card("a", 1), module("a"))
    assert "skeleton:" not in prompt.system_prompt(plain, [])


def test_card_code_field_publish_puts_code(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)
    mods = [module("a", status="ready", cards=1), module("b", "a"), module("c")]
    found = {"a-x": card("a", 1, code=SKELETON), "a-y": card("a", 2)}
    subject(eng.ctx, modules=mods, found=found)
    fake = FakeRtdb()
    sync = CurriculumSync(wiring(fake, eng))

    async def go() -> None:
        assert await sync.publish("car")
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    cards = fake.get("tutor/v1-e2e/subjects/car/cards")
    assert cards["a-x"]["code"] == SKELETON
    assert "code" not in cards["a-y"]
    assert cards["a-x"]["module"] == "a"
    assert cards["a-x"]["suspended"] is False


def test_card_code_field_deck_card_refuses_a_blank_code() -> None:
    raw = card_rules.raw("a-x", card("a", 1))
    with pytest.raises(CardError, match="code must be a non-empty string"):
        validate_card({**raw, "code": "  \n"}, card_rules.topic(module("a")), "a/x")
