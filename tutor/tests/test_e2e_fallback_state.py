# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""scripts/e2e_fallback_state.py: dues, open cards and refusals of the F33 seeder."""

from __future__ import annotations

import runpy
import sys
from typing import TYPE_CHECKING, Any

import pytest

from tutor import unavailable
from tutor.tests._cur import T0, D, card, make_ctx, module, subject, taught
from tutor.tests._fallback_support import NOW, SCRIPTS, car, load, sandbox

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


def test_due_skips_suspended_flagged_and_later(
    mods: tuple[Any, Any], data: Path
) -> None:
    ctx, _ = make_ctx(data)
    found = {c: card("a", i) for i, c in enumerate(("a1", "a2", "a3", "a4"), 1)}
    found["a2"].suspended = True
    subject(ctx, modules=[module("a", status="ready")], found=found)
    for i, cid in enumerate(("a1", "a2", "a3")):
        taught(ctx, "car", cid, T0, i + 1)
    flag = {"dev": "d1", "eid": "01M4QSMFG0JGMMMBEPVFB6D1AC", "k": "flag"}
    ctx.log.append([{**flag, "s": "car", "c": "a3", "at": T0 + 5, "rev": 1}])
    seeder = mods[1].Seeder(data, "car", NOW)
    assert seeder.due(seeder.target, NOW) == ["a1"]
    assert seeder.due(seeder.target, T0) == []
    assert [c for c, _ in seeder.drafted(seeder.ctx.fold())] == ["a1", "a4"]


def test_clear_due_fails_loudly(
    mods: tuple[Any, Any], data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    car(data, a1=T0)
    monkeypatch.setattr(mods[1], "MARGIN_MS", 100 * 365 * D)
    with pytest.raises(mods[1].SeedError, match="still due"):
        mods[1].Seeder(data, "car", NOW).clear_due()


def test_seeder_refuses_real_data_and_planless(
    mods: tuple[Any, Any], data: Path
) -> None:
    with pytest.raises(mods[1].SeedError, match="real data dir"):
        mods[1].Seeder(sys.modules["e2e_seed"].REAL_DATA, "car", NOW)
    car(data)
    bare = data / "subjects" / "bare"
    bare.mkdir()
    (bare / "meta.json").write_text((data / "subjects/car/meta.json").read_text())
    seeder = mods[1].Seeder(data, "car", NOW)
    assert sorted(seeder.views) == ["car", "zed"]
    with pytest.raises(mods[1].SeedError, match="no plan"):
        mods[1].Seeder(data, "bare", NOW)


def test_runs_as_a_script(
    mods: tuple[Any, Any], data: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = SCRIPTS / "e2e_fallback_seed.py"
    monkeypatch.setattr(
        sys, "argv", [str(script), "outage", str(data), "--reason", "network"]
    )
    with pytest.raises(SystemExit) as done:
        runpy.run_path(str(script), run_name="__main__")
    assert done.value.code == 0
    assert [w.reason for w in unavailable.windows(data)] == ["network"]


def test_drafted_takes_open_modules_by_status(
    mods: tuple[Any, Any], data: Path
) -> None:
    """c shows ready in the plan but waits on b: drafted, yet not readable."""
    ctx, _ = make_ctx(data)
    found = {"a1": card("a", 1), "c1": card("c", 1)}
    plan = [
        module("a", status="ready"),
        module("b", "a"),
        module("c", "b", status="ready"),
    ]
    subject(ctx, modules=plan, found=found)
    seeder = mods[1].Seeder(data, "car", NOW)
    assert [c for c, _ in seeder.drafted(seeder.ctx.fold())] == ["a1", "c1"]
    assert seeder.readable() == ["a1"]
    assert mods[0].seed(data, "car", "empty", NOW)["flagged"] == 2
