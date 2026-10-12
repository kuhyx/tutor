# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The subject files: commit bumps rev, cards keep plan order, bad ids refused."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tutor.curriculum.errors import RequestError
from tutor.curriculum.records import Meta, Plan
from tutor.curriculum.subject_store import Change, SubjectStore, read_json, write_json
from tutor.tests._cur import card, module

if TYPE_CHECKING:
    from pathlib import Path


def test_empty_store(tmp_path: Path) -> None:
    store = SubjectStore(tmp_path)
    assert store.subjects() == []
    assert store.meta("car") is None
    assert store.plan("car") is None
    assert store.cards("car") == {}
    assert store.concepts("car") == []
    assert store.profile_raw("car") is None
    with pytest.raises(RequestError, match="unknown subject"):
        store.need_meta("car")
    with pytest.raises(RequestError, match="bad subject id"):
        store.dir("../x")


def test_commit_writes_parts_and_bumps_rev(tmp_path: Path) -> None:
    store = SubjectStore(tmp_path)
    meta = Meta("Cars", "goal", "draft", 1)
    plan = Plan(3, "draft", "", [module("b"), module("a")])
    found = {
        "x": card("a", 1),
        "y": card("b", 2),
        "z": card("b", 1),
        "o": card("gone", 1),
    }
    store.commit("car", meta, Change(plan, found, [{"name": "n"}], {"subject": "car"}))
    assert store.meta("car") == Meta("Cars", "goal", "draft", 1, plan_rev=3, rev=1)
    assert list(store.cards("car")) == ["z", "y", "x", "o"]
    assert store.concepts("car") == [{"name": "n"}]
    assert store.profile_raw("car") == {"subject": "car"}
    store.commit("car", meta)
    assert store.need_meta("car").rev == 2
    (tmp_path / "subjects" / "Bad").mkdir()
    (tmp_path / "subjects" / "nometa").mkdir()
    assert store.subjects() == ["car"]


def test_cards_without_a_plan_keep_order(tmp_path: Path) -> None:
    store = SubjectStore(tmp_path)
    store.commit(
        "car",
        Meta("C", "g", "draft", 1),
        Change(cards={"b": card("m", 2), "a": card("m", 1)}),
    )
    assert list(store.cards("car")) == ["a", "b"]


def test_odd_files_read_as_empty(tmp_path: Path) -> None:
    store = SubjectStore(tmp_path)
    base = tmp_path / "subjects" / "car"
    write_json(base / "cards.json", ["x"])
    write_json(base / "concepts.json", {"x": 1})
    write_json(base / "profile.json", [1])
    write_json(base / "meta.json", [1])
    write_json(base / "plan.json", [1])
    assert store.cards("car") == {}
    assert store.concepts("car") == []
    assert store.profile_raw("car") is None
    assert store.meta("car") is None
    assert store.plan("car") is None
    write_json(base / "cards.json", {"Bad": {}, "ok": card("m", 1).to_json(), "n": 3})
    assert list(store.cards("car")) == ["ok"]
    write_json(base / "concepts.json", [{"name": "a"}, 3])
    assert store.concepts("car") == [{"name": "a"}]
    assert read_json(base / "nothing.json", 7) == 7
    assert json.loads((base / "cards.json").read_text(encoding="utf-8"))["n"] == 3
