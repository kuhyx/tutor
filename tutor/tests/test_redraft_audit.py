# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A redraft's final audit: repair, drop, the hard-card mnemonic."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING, Any

import pytest

from tutor.curriculum import cardgen
from tutor.curriculum.redraft import drain, run
from tutor.tests._cur import T0, review
from tutor.tests._redraft import Fable, car, draft

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(autouse=True)
def _no_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cardgen, "sources", lambda *_: "no search in tests")


@dataclass
class Strict(Fable):
    """A Fable whose judge and audit break the cards a script names, call by call."""

    judge_says: list[set[str]] = field(default_factory=list)
    audit_says: list[set[str]] = field(default_factory=list)

    def _verdicts(self, kind: str, schema: dict[str, Any]) -> dict[str, Any]:
        if kind == "gate":
            return super()._verdicts(kind, schema)
        says = self.audit_says if kind == "audit" else self.judge_says
        bad = says.pop(0) if says else set()
        ids = schema["properties"]["verdicts"]["items"]["properties"]["id"]["enum"]
        return {
            "verdicts": [
                {"id": i, "broken": ["hedged"] if i in bad else [], "why": "opinion"}
                for i in ids
            ]
        }


def _fixed(front: str) -> dict[str, Any]:
    return {**draft("piston", front), "fixes": "piston"}


def _redraft(tmp_path: Path, fable: Strict) -> tuple[Any, dict[str, Any]]:
    ctx, _ = car(tmp_path)
    fable.pairs = [("piston", "old-0"), ("crank", "old-1"), ("valve", "old-2")]
    ctx.draft = fable
    run.start(ctx)
    drain.drain(ctx)
    out = run.root(ctx) / "out/car/a.json"
    return ctx, json.loads(out.read_text())


def _strict(**over: Any) -> Strict:
    return Strict([draft("piston"), draft("crank"), draft("valve")], **over)


def test_a_card_the_audit_fails_is_repaired_and_audited_again(tmp_path: Path) -> None:
    fable = _strict(
        judge_says=[set(), {"piston"}],
        audit_says=[{"piston"}],
        repairs=[_fixed("What does the piston turn?")],
    )
    ctx, out = _redraft(tmp_path, fable)
    assert fable.seen.count("audit") == 2
    assert fable.seen.count("repair") == 1
    assert out["dropped"] == []
    assert out["audit"]["cards"] == 3
    assert out["audit"]["first_pass"]["hedged"] == 1
    assert set(out["audit"]["published"].values()) == {0}
    assert ctx.subjects.cards("car")["old-0"].front == "What does the piston turn?"


def test_a_card_that_fails_both_audits_is_dropped(tmp_path: Path) -> None:
    fable = _strict(audit_says=[{"piston"}, {"piston"}])
    ctx, out = _redraft(tmp_path, fable)
    assert out["dropped"] == ["piston: failed the audit (hedged: opinion)"]
    assert sorted(out["cards"]) == ["crank", "valve"]
    assert ctx.subjects.cards("car")["old-0"].suspended
    assert not ctx.subjects.cards("car")["old-1"].suspended


def test_a_card_the_repair_cannot_fix_is_dropped_after_one_audit(
    tmp_path: Path,
) -> None:
    fable = _strict(judge_says=[set(), {"piston"}], audit_says=[{"piston"}])
    _, out = _redraft(tmp_path, fable)
    assert fable.seen.count("audit") == 1
    assert out["dropped"] == ["piston: failed the audit (hedged: opinion)"]
    assert sorted(out["cards"]) == ["crank", "valve"]
    assert out["audit"]["first_pass"]["hedged"] == 1


def test_a_card_replacing_a_hard_one_needs_a_mnemonic_to_pass(tmp_path: Path) -> None:
    ctx, _ = car(tmp_path)
    review(ctx, "car", "old-0", T0 + 5000, run.AGAIN)  # failed in review: hard
    aided = {**_fixed("What does the piston turn?"), "mnemonic": "push, push, push"}
    fable = _strict(repairs=[aided])
    fable.pairs = [("piston", "old-0"), ("crank", "old-1"), ("valve", "old-2")]
    ctx.draft = fable
    run.start(ctx)
    drain.drain(ctx)
    out = json.loads((run.root(ctx) / "out/car/a.json").read_text())
    assert out["audit"]["first_pass"]["mnemonic"] == 1
    assert out["audit"]["published"]["mnemonic"] == 0
    assert ctx.subjects.cards("car")["old-0"].mnemonic == "push, push, push"
