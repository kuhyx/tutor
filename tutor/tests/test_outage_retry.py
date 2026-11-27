# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A module whose drafting hit Claude's spent limit is drafted again after it."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest

from tutor import outage, unavailable
from tutor.curriculum import cardgen, judge, outage_retry, wiki
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, RequestError
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.tests._cur import make_ctx, module, subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import engine, wiring

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context

NOW = 1_800_000_000.0
END = NOW + 600
SOURCES = [
    wiki.Source("https://en.wikipedia.org/wiki/A", "A", "text a"),
    wiki.Source("https://en.wikibooks.org/wiki/B", "B", "text b"),
]


def _spent() -> RequestError:
    """What ``ask_draft`` raises on a spent limit (the window is recorded)."""
    cause = outage.record(outage.ClaudeUnavailableError("rate_limit", int(END)), NOW)
    err = RequestError(CLAUDE_UNAVAILABLE, str(cause))
    err.__cause__ = cause
    return err


def _state(ctx: Context, mid: str = "a") -> tuple[str, str | None]:
    plan = ctx.subjects.plan("car")
    assert plan is not None
    found = plan.module(mid)
    assert found is not None
    return found.status, found.error_kind


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Context:
    made, fakes = make_ctx(tmp_path)
    monkeypatch.setattr(cardgen, "sources", lambda *_: list(SOURCES))
    monkeypatch.setattr(judge, "gate", lambda _c, _s, cards, _t, _k: (cards, []))
    subject(made, modules=[module("a", status="generating"), module("b", "a")])
    fakes.replies.append(_spent())
    return made


def test_a_spent_draft_fails_then_is_drafted_again_after_the_reset(
    ctx: Context,
) -> None:
    result = cardgen.generate(ctx, "car", "a")
    assert (result["status"], result["error_kind"]) == ("failed", "claude_limit")
    recent: dict[tuple[str, str], float] = {}
    assert outage_retry.retry(ctx, NOW + 60, recent) == []  # window still open
    assert _state(ctx) == ("failed", "claude_limit")
    assert outage_retry.retry(ctx, END + 1, recent) == [("car", "a")]
    assert _state(ctx) == ("generating", None)


def test_one_retry_per_window_span(ctx: Context) -> None:
    cardgen.generate(ctx, "car", "a")
    recent = {("car", "a"): END}  # retried at END: failed again at once
    assert outage_retry.retry(ctx, END + 1, recent) == []
    later = END + unavailable.DEFAULT_SPAN + 1
    assert outage_retry.retry(ctx, later, recent) == [("car", "a")]
    assert recent[("car", "a")] == later


def test_other_failures_and_archived_subjects_stay_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made, _ = make_ctx(tmp_path)
    mods = [module("a", status="failed", error="x", error_kind="model_failed")]
    subject(made, modules=mods)
    spent = [module("a", status="failed", error="x", error_kind="claude_limit")]
    subject(made, "old", modules=spent)
    subject(made, "draft", plan_status="proposed", modules=spent)
    monkeypatch.setattr(type(made), "archived", lambda _self: {"old"})
    assert outage_retry.retry(made, END + 1, {}) == []


def test_sync_queues_the_module_once_the_window_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    failed = module("a", status="failed", error="spent", error_kind="claude_limit")
    subject(eng.ctx, modules=[failed])
    unavailable.record("rate_limit", NOW, END)
    clock = [NOW + 60]
    sync = CurriculumSync(wiring(FakeRtdb(), eng, now=lambda: clock[0]))
    monkeypatch.setattr(sync, "pull", _noop)
    monkeypatch.setattr(sync, "push", _noop)

    async def go() -> None:
        await sync.sync()
        assert sync.queue.empty()
        clock[0] = END + 1
        await sync.sync()
        assert sync.queue.get_nowait() == ("car", "a")
        await sync.w.rtdb.aclose()

    asyncio.run(go())


async def _noop(*_: Any) -> None:
    return None
