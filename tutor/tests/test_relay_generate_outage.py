# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A module drafted while Claude's limit is spent is drafted again after it."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from tutor import outage, unavailable
from tutor.curriculum import handlers as cur
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, RequestError
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.tests._cur import subject
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._relay_support import engine, wiring

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tutor.curriculum.context import Context

NOW = 1_800_000_000.0


def _spent(_ctx: Context, _subject: str, _module: str) -> dict[str, Any]:
    """What ``cardgen.generate`` raises when ``ask_draft`` hits the limit."""
    err = outage.record(outage.ClaudeUnavailableError("rate_limit", int(NOW) + 600))
    raise RequestError(CLAUDE_UNAVAILABLE, str(err)) from err


async def _drain(sync: CurriculumSync, made: list[str], want: int) -> None:
    """Run the generator until ``want`` calls were made and the queue is empty."""
    task = asyncio.create_task(sync.generate_forever())
    for _ in range(200):
        await asyncio.sleep(0.01)
        if len(made) >= want and sync.queue.empty():
            break
    await asyncio.sleep(0.02)
    task.cancel()


def test_a_spent_limit_defers_the_module_until_the_window_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    subject(eng.ctx, "car")
    clock = [NOW]
    sync = CurriculumSync(wiring(FakeRtdb(), eng, now=lambda: clock[0]))
    made: list[str] = []
    calls = {"n": 0}

    def generate(ctx: Context, subj: str, module: str) -> dict[str, Any]:
        made.append(module)
        calls["n"] += 1
        if calls["n"] == 1:
            return _spent(ctx, subj, module)
        return {}  # drafted: the module leaves ``generating``

    def fold(_ctx: Context) -> dict[str, Any]:
        return {"changed": [], "generate": [["car", "b"]] if calls["n"] < 2 else []}

    monkeypatch.setattr(cur, "fold_and_advance", fold)
    monkeypatch.setattr(cur, "generate", generate)

    async def go() -> None:
        await sync.sync()
        await _drain(sync, made, 1)
        assert unavailable.current(NOW) is not None
        await sync.sync()  # window still open: not queued, no CLI spawned
        assert sync.queue.empty()
        clock[0] = NOW + 601
        await sync.sync()  # the limit reset: drafted again
        assert sync.queue.qsize() == 1
        await _drain(sync, made, 2)
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    assert made == ["b", "b"]


def test_an_open_window_skips_the_draft_without_spawning_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eng, _ = engine(tmp_path)
    subject(eng.ctx, "car")
    unavailable.record("rate_limit", NOW, NOW + 600)
    sync = CurriculumSync(wiring(FakeRtdb(), eng, now=lambda: NOW))
    made: list[str] = []
    monkeypatch.setattr(
        cur, "fold_and_advance", lambda _c: {"changed": [], "generate": [["car", "b"]]}
    )

    def generate(_ctx: Context, _subj: str, module: str) -> dict[str, Any]:
        made.append(module)
        return {}

    monkeypatch.setattr(cur, "generate", generate)

    async def go() -> None:
        sync.queue.put_nowait(("car", "b"))
        await _drain(sync, made, 0)
        await sync.sync()
        assert sync.queue.empty()
        await sync.w.rtdb.aclose()

    asyncio.run(go())
    assert made == []
