# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Regression: module 1 of "how a car works" kept module 2's cards.

The repair of 448063f (``car_overview.json``, replayed by the code of that
commit) left the "Car" module with cards on pistons, the crankshaft and gear
ratios, which the later "Internal combustion engine" and "Transmission"
modules teach. ``car_overview_scope.json`` records a real ``regenerate --now``
from exactly that state (``what-is-car`` taught) with the plan-aware gate:
those cards must be suspended as belonging to the later modules, the taught
card must never reach the gate, and the replacements must stay in module 1.
Page texts: Wikipedia contributors, CC BY-SA 4.0, clipped.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import TYPE_CHECKING

from tutor.curriculum import regen
from tutor.curriculum.plan_context import SCOPE_RULE
from tutor.tests.test_relevance_fixture import load

if TYPE_CHECKING:
    import pytest

FIXTURE = Path(__file__).parent / "data" / "cardgen" / "car_overview_scope.json"
ENGINE = "internal-combustion-engine"
GEARS = "transmission-gears"
LATER = {
    "piston-force-path": ENGINE,
    "crankshaft-role": ENGINE,
    "force-over-distance": ENGINE,
    "why-multiple-gears": GEARS,
    "manual-vs-automatic": GEARS,
}
MECHANISM = re.compile(r"piston|crankshaft|connecting rod|gear ratio", re.IGNORECASE)


def test_later_module_cards_are_suspended_and_replaced_in_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ctx, fakes, data = load(FIXTURE, tmp_path, monkeypatch)
    subject, module = data["subject"], data["module"]
    before = ctx.subjects.cards(subject)
    assert all(not before[cid].suspended for cid in LATER)
    assert data["before"]["taught"] == ["what-is-car"]

    assert regen.main([subject, module, "--now"], lambda _root: ctx) == 0
    assert not fakes.replies  # every recorded call was made, in order
    out = json.loads(capsys.readouterr().out)

    cards = ctx.subjects.cards(subject)
    for cid, owner in LATER.items():
        assert cards[cid].suspended, cid
        assert any(
            w.startswith(f"{cid}: belongs to later module {owner}") for w in out["why"]
        )
    assert out["taught"] == ["what-is-car"]
    assert not cards["what-is-car"].suspended
    assert cards["what-is-car"] == before["what-is-car"]  # never touched

    live = {c: r for c, r in cards.items() if r.module == module and not r.suspended}
    assert len(live) >= 6
    fresh = [r for c, r in live.items() if c not in before]
    assert fresh
    assert not [r.front for r in fresh if MECHANISM.search(f"{r.front} {r.back}")]
    plan = ctx.subjects.plan(subject)
    assert plan is not None
    current = plan.module(module)
    assert current is not None
    assert (current.status, current.cards, current.error) == ("ready", len(live), None)


def test_every_call_sees_the_later_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, fakes, data = load(FIXTURE, tmp_path, monkeypatch)
    regen.main([data["subject"], data["module"], "--now"], lambda _root: ctx)
    engine = "How burning fuel and air in a cylinder pushes a piston"
    assert len(fakes.prompts) == len(data["model"])
    assert all(engine in prompt for _, prompt in fakes.prompts)
    gate = fakes.prompts[0][1]
    assert '"what-is-car"' not in gate  # taught: never gated
    assert '"piston-force-path"' in gate
    draft = next(p for s, p in fakes.prompts if s.startswith("You write flashcards"))
    assert "piston-force-path" not in draft.split("Existing cards", 1)[1]
    assert SCOPE_RULE in next(s for s, _ in fakes.prompts if s.startswith("You write"))
