# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_fallback*.py (F33): the checks on sandbox files and page rects."""

from __future__ import annotations

import importlib
import json
import sys
from typing import TYPE_CHECKING, Any

import pytest

from tutor.tests._cur import T0
from tutor.tests._fallback_support import NOW, SCRIPTS, car, sandbox

if TYPE_CHECKING:
    from pathlib import Path

FRESH = ("e2e_seed", "e2e_gate", "e2e_fallback_state", "e2e_fallback_checks")


@pytest.fixture
def mods(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The F33 flow modules, imported fresh from scripts/."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    names = (*FRESH, "e2e_fallback", "e2e_fallback_sheet")
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)
    return {name: importlib.import_module(name) for name in names}


def _ev(kind: str, card: str, at: int, **extra: Any) -> dict[str, Any]:
    return {"k": kind, "s": "car", "c": card, "at": at, **extra}


def test_read_problems_pass_and_name_what_is_missing(mods: dict[str, Any]) -> None:
    check = mods["e2e_fallback_checks"].read_problems
    good = [
        _ev("taught", "a1", 10),
        _ev("unchecked", "a1", 11, src="read"),
        _ev("taught", "a2", 12),
        _ev("unchecked", "a2", 13, src="read"),
        _ev("review", "a2", 14, r=1),
    ]
    assert check(good, ("car", "a1"), ("car", "a2"), 10) == []
    late = check(good, ("car", "a1"), ("car", "a2"), 12)
    assert late == [
        "('car', 'a1'): no taught event",
        "('car', 'a1'): no unchecked event with src read",
    ]
    swapped = check(good, ("car", "a2"), ("car", "a1"), 0)
    assert swapped == [
        "('car', 'a2'): rated got it but reviewed Again",
        "('car', 'a1'): no review rated 1",
    ]


def test_read_rows_keep_new_read_credit_only(
    mods: dict[str, Any], tmp_path: Path
) -> None:
    rows = [
        {"kind": "credit", "created_at": 5, "detail": {"session_id": "read-1"}},
        {"kind": "credit", "created_at": 1, "detail": {"session_id": "read-0"}},
        {"kind": "credit", "created_at": 6, "detail": {"session_id": "drill-1"}},
        {"kind": "carry", "created_at": 7, "detail": {"session_id": "read-2"}},
        {"kind": "credit", "created_at": 8},
    ]
    (tmp_path / "ledger.json").write_text(json.dumps({"entries": rows}))
    got = mods["e2e_fallback_checks"].read_rows(tmp_path, 2)
    assert [r["detail"]["session_id"] for r in got] == ["read-1"]


def test_run_active_pairs_each_rating_with_its_last_prompt(
    mods: dict[str, Any], tmp_path: Path
) -> None:
    run_active = mods["e2e_fallback_checks"].run_active
    assert run_active(tmp_path) == 0.0
    lines = [
        {"type": "prompt", "card": "a1", "logged_at": 100},
        {"type": "prompt", "card": "a1", "logged_at": 110},  # read mode asks again
        {"type": "rate", "card": "a1", "logged_at": 130},
        {"type": "credit", "logged_at": 130},
        {"type": "rate", "card": "zz", "logged_at": 140},  # no prompt: skipped
        {"type": "prompt", "card": "a2", "logged_at": 150},
        {"type": "rate", "card": "a2", "logged_at": 165.5},
    ]
    (tmp_path / "read").mkdir()
    (tmp_path / "read" / "read-20261127-000000-aaaa.jsonl").write_text("{}\n")
    newest = tmp_path / "read" / "read-20261127-100000-bbbb.jsonl"
    newest.write_text("".join(json.dumps(line) + "\n" for line in lines))
    assert run_active(tmp_path) == 35.5


def test_labels_and_counts(mods: dict[str, Any]) -> None:
    checks = mods["e2e_fallback_checks"]
    labels = ["Review A (3 due)", "Review all (5 due)", "Review (5 due)", "Plan"]
    assert checks.due_labels(labels) == {"A": 3}
    assert checks.left_count("Back\n53 left\nShow") == 53
    assert checks.left_count("no count") is None


def test_outside_flags_rects_past_the_viewport(mods: dict[str, Any]) -> None:
    rect = {"left": 0, "top": 0, "right": 412, "bottom": 915.5}
    low = {**rect, "bottom": 920}
    wide = {**rect, "left": -3}
    assert mods["e2e_fallback_checks"].outside([rect, low, wide], 412, 915) == [
        low,
        wide,
    ]


def test_due_by_module_and_titles(mods: dict[str, Any], tmp_path: Path) -> None:
    data = sandbox(tmp_path)
    car(data, a1=T0)
    checks = mods["e2e_fallback_checks"]
    assert checks.due_by_module(data, "car", NOW) == {"a": 1}
    assert checks.module_titles(data, "car") == {"a": "A", "b": "B"}


def test_tile_glyph_skips_homes_own_review(mods: dict[str, Any]) -> None:
    pick = mods["e2e_fallback_sheet"].tile_glyph
    home = {"top": 446, "left": 184}
    tile = {"top": 296, "left": 1112}
    assert pick([home, tile], {"top": 444}) is tile
    with pytest.raises(mods["e2e_fallback_sheet"].FlowError, match="one subject"):
        pick([home], {"top": 444})


def test_out_prefix_and_phone_viewport(mods: dict[str, Any]) -> None:
    flow = mods["e2e_fallback"]
    assert flow.out_prefix("app/x", {}) == "app/x"
    assert flow.out_prefix("app/x", {"E2E_SHOTS": "/s"}) == "/s/f33"
    calls: list[tuple[str, dict[str, Any]]] = []

    class Fake:
        def call(self, method: str, **params: Any) -> None:
            calls.append((method, params))

    flow.phone_viewport(Fake(), (412, 915))
    assert calls == [
        (
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 412,
                "height": 915,
                "deviceScaleFactor": 1,
                "mobile": False,
                "screenWidth": 412,
                "screenHeight": 915,
            },
        )
    ]
