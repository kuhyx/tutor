# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``redraft deck``: the live subject written back to the repo deck."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tutor.curriculum.errors import RequestError
from tutor.curriculum.redraft import cli, deck
from tutor.curriculum.subject_store import Change
from tutor.tests._cur import card, make_ctx, module, subject

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context


def _automation(tmp_path: Path) -> Context:
    ctx, _ = make_ctx(tmp_path / "data")
    found = {
        "a1": card("a", 1),
        "a2": card("a", 2, "a1", mnemonic="think of two"),
        "gone": card("a", 3, suspended=True),
        "b1": card("b-c", 1),
    }
    mods = [module("a", status="ready"), module("b-c", "a"), module("d", "b-c")]
    subject(ctx, deck.SUBJECT, modules=mods, found=found)
    return ctx


def test_the_deck_is_rewritten_from_the_live_cards(tmp_path: Path) -> None:
    ctx = _automation(tmp_path)
    out = tmp_path / "deck"
    out.mkdir()
    (out / "retired.json").write_text("[]")
    (out / "a.json").write_text("[]")  # a topic the plan still has
    assert deck.export(ctx, out) == {"a": 2, "b_c": 1}
    assert sorted(p.name for p in out.glob("*.json")) == [
        "a.json",
        "b_c.json",
        "manifest.json",
    ]
    first = json.loads((out / "a.json").read_text())
    assert [c["id"] for c in first] == ["a1", "a2"]
    assert first[0].keys() == {"id", "front", "back", "source", "excerpt"}
    assert (first[1]["requires"], first[1]["mnemonic"]) == (["a1"], "think of two")
    manifest = json.loads((out / "manifest.json").read_text())
    assert [(m["stem"], m["title"]) for m in manifest] == [("a", "A"), ("b_c", "B C")]


def test_a_missing_subject_writes_nothing(tmp_path: Path) -> None:
    ctx, _ = make_ctx(tmp_path / "data")
    out = tmp_path / "deck"
    with pytest.raises(RequestError, match="no automation subject"):
        deck.export(ctx, out)
    assert not out.exists()


def test_a_deck_the_loader_would_refuse_is_never_written(tmp_path: Path) -> None:
    ctx = _automation(tmp_path)
    cards = ctx.subjects.cards(deck.SUBJECT)
    cards["a1"].requires = ["nowhere"]
    meta = ctx.subjects.need_meta(deck.SUBJECT)
    ctx.subjects.commit(deck.SUBJECT, meta, Change(cards=cards))
    out = tmp_path / "deck"
    with pytest.raises(RequestError, match="nowhere"):
        deck.export(ctx, out)
    assert not out.exists()


def test_the_cli_exports_to_the_named_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _automation(tmp_path)
    out = tmp_path / "deck"
    assert cli.main(["deck", "--out", str(out)], lambda _p: ctx) == 0
    assert json.loads(capsys.readouterr().out) == {"a": 2, "b_c": 1}
    assert (out / "manifest.json").is_file()
