# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Records: validation, unknown keys dropped, size caps, the module DAG."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from tutor.curriculum.errors import RequestError
from tutor.curriculum.records import (
    CardRec,
    Meta,
    Module,
    Plan,
    check_modules,
    id_list,
    plan_json,
    text,
)
from tutor.tests._cur import card, module


def test_text_limits_and_empty() -> None:
    assert text({"t": " a "}, "t", 5) == "a"
    assert text({}, "t", 5, empty=True) == ""
    for raw in ({"t": "x" * 6}, {"t": 3}, {"t": " "}):
        with pytest.raises(RequestError, match="t must"):
            text(raw, "t", 5)


def test_id_list() -> None:
    assert id_list(["a", "b"], "requires") == ["a", "b"]
    with pytest.raises(RequestError, match="list of ids"):
        id_list(["A"], "requires")
    with pytest.raises(RequestError, match="list of ids"):
        id_list("a", "requires")
    with pytest.raises(RequestError, match="duplicates"):
        id_list(["a", "a"], "requires")


def test_meta_round_trip_and_errors() -> None:
    meta = Meta("T", "goal", "draft", 5, error="x")
    assert Meta.from_json(asdict(meta)) == meta
    assert Meta.from_json({**asdict(meta), "error": 3}).error is None
    with pytest.raises(RequestError, match="unknown subject status"):
        Meta.from_json({**asdict(meta), "status": "odd"})
    with pytest.raises(RequestError, match="created must be an integer"):
        Meta.from_json({**asdict(meta), "created": True})


def test_module_client_keeps_only_editable_fields() -> None:
    raw = {"id": "m", "title": "M", "status": "ready", "cards": 9, "junk": 1}
    assert Module.from_json(raw, client=True).status == "locked"
    stored = Module.from_json({**raw, "error": "boom", "recall": 0.5})
    assert (stored.status, stored.cards, stored.error, stored.recall) == (
        "ready",
        9,
        "boom",
        0.5,
    )
    assert Module.from_json({**raw, "error": 1}).error is None
    with pytest.raises(RequestError, match="valid id"):
        Module.from_json({"id": "Bad"})
    with pytest.raises(RequestError, match="valid id"):
        Module.from_json("m")
    with pytest.raises(RequestError, match="prefixes"):
        Module.from_json({**raw, "prefixes": [""]})
    with pytest.raises(RequestError, match="unknown module status"):
        Module.from_json({**raw, "status": "odd"})


def test_plan_round_trip() -> None:
    plan = Plan(2, "approved", "n", [module("a"), module("b", "a")], [{"rev": 1}])
    back = Plan.from_json(plan_json(plan))
    assert back == plan
    assert back.module("b") is back.modules[1]
    assert back.module("z") is None
    assert (
        Plan.from_json({**plan_json(plan), "status": "weird", "history": [1]}).status
        == "draft"
    )
    with pytest.raises(RequestError, match="modules list"):
        Plan.from_json({"rev": 1})


def test_plan_size_cap() -> None:
    plan = Plan(
        1, "draft", "n", [Module(f"m{i}", "x" * 120, "s" * 300) for i in range(60)]
    )
    with pytest.raises(RequestError, match="16000 bytes"):
        plan_json(plan)


def test_check_modules() -> None:
    check_modules([module("a"), module("b", "a"), module("c")])
    with pytest.raises(RequestError, match="3-12 modules, not 2"):
        check_modules([module("a"), module("b")])
    with pytest.raises(RequestError, match="duplicate"):
        check_modules([module("a"), module("a"), module("c")])
    with pytest.raises(RequestError, match="not earlier"):
        check_modules([module("a", "b"), module("b"), module("c")])
    # A go-deeper round counts only its own (deepest) modules.
    old = [module("a"), module("b")]
    new = [Module(f"n{i}", "N", depth=2) for i in range(3)]
    check_modules([*old, *new])


def test_card_round_trip_and_cap() -> None:
    rec = card("a", 1)
    assert CardRec.from_json({**rec.to_json(), "junk": 1}) == rec
    with pytest.raises(RequestError, match="2000 bytes"):
        card("a", 1, back="x" * 2100).to_json()
