# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``TUTOR_CARD_WORK=off``: the background card work never starts."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tutor.relay import redraft_task
from tutor.tests.test_redraft_task import _work

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_card_work_ends_at_once_when_switched_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, _ = _work(tmp_path)
    rounds: list[int] = []

    async def once() -> str:
        rounds.append(1)
        return "idle"

    monkeypatch.setattr(work, "once", once)
    monkeypatch.setenv(redraft_task.SWITCH_ENV, "off")
    asyncio.run(asyncio.wait_for(work.run(), 5))
    assert rounds == []
