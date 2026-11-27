# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_fallback_seed.py: each F33 branch holds by the server's own pickers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor import unavailable
from tutor.curriculum.context import Context
from tutor.tests._cur import T0, D, card, make_ctx, module, subject, taught
from tutor.tests._fallback_support import MIN, NOW, car, load, sandbox

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mods(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any]:
    """``e2e_fallback_seed`` and ``e2e_fallback_state``, as `up` runs them."""
    return load(monkeypatch)


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """A sandbox data dir whose worker is ``dev-pc``."""
    return sandbox(tmp_path)


def test_due_keeps_two_due_and_clears_the_rest(
    mods: tuple[Any, Any], data: Path
) -> None:
    car(data, a1=T0, a2=T0)
    got = mods[0].seed(data, "car", "due", NOW)
    assert sorted(got["due"]) == ["a1", "a2"]
    assert got["cleared"] == 1  # zed's z1
    seeder = mods[1].Seeder(data, "car", NOW)
    assert seeder.due(seeder.views["zed"], NOW + mods[1].MARGIN_MS) == []
    assert json.loads((data.parent / "f33_seed.json").read_text()) == got


def test_due_teaches_fresh_cards_a_month_back(
    mods: tuple[Any, Any], data: Path
) -> None:
    car(data, a1=T0)
    got = mods[0].seed(data, "car", "due", NOW)
    assert sorted(got["due"]) == ["a1", "a2", "a3"]


def test_due_refuses_with_no_fresh_card(mods: tuple[Any, Any], data: Path) -> None:
    car(data, a1=T0, a2=NOW - MIN, a3=NOW - MIN, a4=NOW - MIN)
    with pytest.raises(mods[1].SeedError, match="1 card"):
        mods[0].seed(data, "car", "due", NOW)


def test_read_has_three_already(mods: tuple[Any, Any], data: Path) -> None:
    car(data, a1=T0)
    got = mods[0].seed(data, "car", "read", NOW)
    assert got["read"] == ["a2", "a3", "a4"]
    assert got["cleared"] == 2  # a1 and z1
    seeder = mods[1].Seeder(data, "car", NOW)
    assert all(
        not seeder.due(v, NOW + mods[1].MARGIN_MS) for v in seeder.views.values()
    )


def test_read_untaughts_the_module_tail(mods: tuple[Any, Any], data: Path) -> None:
    car(data, a1=NOW - MIN, a2=NOW - MIN, a3=NOW - MIN)
    assert mods[0].seed(data, "car", "read", NOW)["read"] == ["a2", "a3", "a4"]


def test_read_reopens_a_fully_taught_module(mods: tuple[Any, Any], data: Path) -> None:
    car(data, a1=NOW - MIN, a2=NOW - MIN, a3=NOW - MIN, a4=NOW - MIN)
    assert mods[0].seed(data, "car", "read", NOW)["read"] == ["a2", "a3", "a4"]


def test_read_refuses_a_short_module(mods: tuple[Any, Any], data: Path) -> None:
    car(data, n=2)
    with pytest.raises(mods[1].SeedError, match="only 2 readable"):
        mods[0].seed(data, "car", "read", NOW)


def test_drill_teaches_every_open_card(mods: tuple[Any, Any], data: Path) -> None:
    car(data, a1=T0)
    got = mods[0].seed(data, "car", "drill", NOW)
    assert (got["taught"], got["newly_taught"]) == (4, ["a2", "a3", "a4"])
    assert got["archived"] == ["zed"]
    ctx = Context(data, device="x")
    assert ctx.archived() == {"zed"}
    assert mods[1].Seeder(data, "car", NOW).readable() == []


def test_drill_refuses_with_nothing_to_teach(mods: tuple[Any, Any], data: Path) -> None:
    ctx, _ = make_ctx(data)
    subject(ctx, modules=[module("a", status="ready")], found={})
    with pytest.raises(mods[1].SeedError, match="0 taught"):
        mods[0].seed(data, "car", "drill", NOW)


def test_empty_untaughts_flags_and_clears_the_deck(
    mods: tuple[Any, Any], data: Path
) -> None:
    car(data, a1=T0)
    (data / "progress.json").write_text(json.dumps({"cards_done": {"x": {}}, "k": 1}))
    got = mods[0].seed(data, "car", "empty", NOW)
    assert (got["flagged"], got["archived"]) == (4, ["zed"])
    assert json.loads((data / "progress.json").read_text()) == {
        "cards_done": {},
        "k": 1,
    }
    seeder = mods[1].Seeder(data, "car", NOW)
    assert seeder.ctx.fold().taught_ids("car") == set()
    assert seeder.readable() == []
    assert seeder.drafted(seeder.ctx.fold()) == []


def test_empty_without_progress(mods: tuple[Any, Any], data: Path) -> None:
    car(data)
    assert mods[0].seed(data, "car", "empty", NOW)["flagged"] == 4
    assert not (data / "progress.json").exists()


def test_empty_refuses_when_cards_stay(
    mods: tuple[Any, Any], data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    car(data)
    monkeypatch.setattr(mods[1].Seeder, "readable", lambda _self: ["a1"])
    with pytest.raises(mods[1].SeedError, match="still has"):
        mods[0].seed(data, "car", "empty", NOW)


def test_main_outage_and_seed(
    mods: tuple[Any, Any],
    data: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert (
        mods[0].main(
            [
                "outage",
                str(data),
                "--reason",
                "rate_limit",
                "--at",
                "2026-11-27 10:00:00",
            ]
        )
        == 0
    )
    (window,) = unavailable.windows(data)
    assert (window.reason, window.end - window.start) == ("rate_limit", 7200)
    assert "rate_limit outage until" in capsys.readouterr().out
    car(data, a1=T0, a2=T0)
    at = ["--at", datetime.fromtimestamp(NOW / 1000, tz=UTC).isoformat(" ")]
    assert (
        mods[0].main(["seed", str(data), "--subject", "car", "--branch", "due", *at])
        == 0
    )
    assert '"branch": "due"' in capsys.readouterr().out
    assert (
        mods[0].main(["seed", str(data), "--subject", "nope", "--branch", "due"]) == 1
    )
    assert "no plan" in caplog.text


def test_gate_leaves_the_last_two_readable(mods: tuple[Any, Any], data: Path) -> None:
    ctx, _ = make_ctx(data)
    found = {f"a{i}": card("a", i) for i in range(1, 5)}
    found |= {"b1": card("b", 1), "b2": card("b", 2)}
    subject(
        ctx,
        modules=[module("a", status="ready"), module("b", status="ready")],
        found=found,
    )
    for i in range(1, 5):
        taught(ctx, "car", f"a{i}", NOW - 2 * D, i)
    got = mods[0].seed(data, "car", "gate", NOW)
    assert (got["read"], got["module"], got["next_module"]) == (["a3", "a4"], "a", "b")
    assert mods[1].Seeder(data, "car", NOW).readable() == ["a3", "a4"]


def test_gate_refuses_when_the_tail_stays_unreadable(
    mods: tuple[Any, Any], data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    car(data, a1=T0)
    monkeypatch.setattr(mods[0], "gate_seed", lambda *_: {"unpassed": ["b1"]})
    with pytest.raises(mods[1].SeedError, match="want \\['b1'\\]"):
        mods[0].seed(data, "car", "gate", NOW)
