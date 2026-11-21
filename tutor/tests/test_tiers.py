# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Model tiers: Fable 5.2 at xhigh drafts cards, Sonnet at high repeats."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tutor import tiers
from tutor.curriculum import cardgen, judge, modelcall, regen, wiki
from tutor.curriculum.context import Context
from tutor.session import Reply
from tutor.tests._cur import card, make_ctx, module, subject
from tutor.tests.test_cardgen import SOURCES, drafted

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_the_two_tiers() -> None:
    assert (tiers.DRAFT.model, tiers.DRAFT.effort) == ("claude-fable-5-2", "xhigh")
    assert (tiers.REPEAT.model, tiers.REPEAT.effort) == ("claude-sonnet-5-5", "high")
    assert tiers.DRAFT.timeout > tiers.REPEAT.timeout


def test_options_carry_the_tier(tmp_path: Path) -> None:
    del tmp_path
    made = modelcall.options("sys", {"type": "object"}, tiers.DRAFT)
    assert (made.model, made.effort) == ("claude-fable-5-2", "xhigh")
    plain = modelcall.options("sys", {"type": "object"})
    assert (plain.model, plain.effort) == ("claude-sonnet-5-5", "medium")


def test_context_defaults(tmp_path: Path) -> None:
    ctx = Context(tmp_path, device="d")
    assert ctx.model is modelcall.ask_repeat
    assert ctx.draft is modelcall.ask_draft
    assert ctx.drafting().model is modelcall.ask_draft


def test_each_call_logs_its_model_and_effort(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    seen: list[tuple[Any, float]] = []

    class Session:
        def __init__(self, options: Any, timeout: float) -> None:
            seen.append((options, timeout))

        async def ask_raw(self, prompt: str) -> Reply:
            await asyncio.sleep(0)
            return Reply({"ok": prompt}, "", {}, 0, 0.0)

        async def close(self) -> None:
            await asyncio.sleep(0)

    monkeypatch.setattr(modelcall, "TutorSession", Session)
    with caplog.at_level(logging.WARNING):
        assert modelcall.ask_draft("s", "p", {}) == {"ok": "p"}
        assert modelcall.ask_repeat("s", "q", {}) == {"ok": "q"}
    assert [(o.model, o.effort, t) for o, t in seen] == [
        ("claude-fable-5-2", "xhigh", tiers.DRAFT.timeout),
        ("claude-sonnet-5-5", "high", tiers.REPEAT.timeout),
    ]
    assert "claude-fable-5-2 at xhigh" in caplog.text
    assert "claude-sonnet-5-5 at high" in caplog.text


def _gen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **mod: Any) -> Any:
    ctx, fakes = make_ctx(tmp_path)
    used: list[str] = []

    def draft(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        used.append("draft")
        return fakes.model(system, prompt, schema)

    def repeat(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        used.append("repeat")
        return fakes.model(system, prompt, schema)

    ctx.draft, ctx.model = draft, repeat
    found: list[wiki.Source] = list(SOURCES)
    monkeypatch.setattr(cardgen, "sources", lambda *_: found)
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    subject(
        ctx,
        modules=[module("a", status="generating", **mod), module("b", "a")],
        found={"old": card("z", 1)},
    )
    fakes.replies = [drafted(4)]
    return ctx, used


def test_a_new_module_is_drafted_by_the_draft_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, used = _gen(tmp_path, monkeypatch)
    assert cardgen.generate(ctx, "car", "a")["status"] == "ready"
    assert set(used) == {"draft"}  # the draft and its judge


def test_a_regenerated_module_is_drafted_by_the_repeat_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, used = _gen(tmp_path, monkeypatch, repeat=True)
    assert cardgen.generate(ctx, "car", "a")["status"] == "ready"
    assert set(used) == {"repeat"}
    plan = ctx.subjects.plan("car")
    assert plan is not None
    assert plan.module("a").repeat is False


def test_regenerate_marks_the_module_repeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _ = make_ctx(tmp_path)
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    subject(ctx, modules=[module("a", status="ready"), module("b", "a")])
    regen.regenerate(ctx, "car", "a")
    plan = ctx.subjects.plan("car")
    assert plan is not None
    mod = plan.module("a")
    assert mod is not None
    assert (mod.status, mod.repeat) == ("generating", True)
    raw = (tmp_path / "subjects/car/plan.json").read_text()
    assert '"repeat": true' in raw
    assert raw.count('"repeat"') == 1  # unset: the old shape
