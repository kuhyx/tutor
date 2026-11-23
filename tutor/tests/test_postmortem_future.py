# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``apply-postmortem``: the approved future-module part of the latest revision."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor import sources
from tutor.curriculum import card_ops, regen
from tutor.curriculum.context import Context
from tutor.curriculum.errors import RequestError
from tutor.postmortem import future, report
from tutor.store import data_dir
from tutor.tests import _pm

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

CARD = {
    "front": "What does diff[s] += 1 mark?",
    "back": "Where a range starts.",
    "why": "w",
}


def _report(*futures: object) -> None:
    entry = {"unit": _pm.UNIT, "rev": 1, "future": list(futures)}
    assert report.save(_pm.LC, _pm.UNIT, entry)


def _ctx(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, teach: bool) -> Context:
    monkeypatch.setattr(sources, "CACHE_DIR", tmp_path / "src-cache")
    ctx = Context(data_dir())
    _pm.unit_subject(ctx, teach=teach)
    return ctx


def test_an_untaught_module_is_regenerated_then_gains_the_cards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _ctx(monkeypatch, tmp_path, teach=True)
    regenerated: list[str] = []
    monkeypatch.setattr(regen, "regenerate", lambda _c, _s, m: regenerated.append(m))
    _report({"module": "b", "cards": [CARD]}, {"module": "a", "cards": []}, "junk")

    assert future.main([_pm.UNIT], make=lambda _d: ctx) == 0

    assert regenerated == ["b"]  # a has taught cards: it is never regenerated
    assert capsys.readouterr().out.splitlines() == [
        "b: regenerated + 1 card(s)",
        "a: 0 card(s)",
    ]
    fronts = [c.front for c in ctx.subjects.cards(_pm.LC).values() if c.module == "b"]
    assert CARD["front"] in fronts


def test_module_filter_refusals_and_no_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = _ctx(monkeypatch, tmp_path, teach=True)
    assert future.main([_pm.UNIT], make=lambda _d: ctx) == 1
    assert "no signed post-mortem proposal" in capsys.readouterr().out
    _report({"module": "b", "cards": [CARD]}, {"module": "a", "cards": [CARD]})
    monkeypatch.setattr(regen, "regenerate", lambda *_a: None)

    def refuse(*_a: Any, **_k: Any) -> Any:
        code, msg = "edit_refused", "refused"
        raise RequestError(code, msg)

    monkeypatch.setattr(card_ops, "add", refuse)
    assert future.run(ctx, _pm.UNIT, ["a"]) == ["a: 0 card(s)"]
    assert future.latest("other") is None
