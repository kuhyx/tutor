# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The server's background card work: the redraft queue, then stale paths.

Every 30 s: while a redraft run (``curriculum.redraft``) has pending units,
drain it (in threads; each real model call first waits until no reply is in
flight, so the learner's chat never queues behind a draft) and sync the
curriculum, which publishes the swapped subjects. Otherwise write one open
module's stale interrogation paths (``curriculum.paths``; a card edit made
them stale). Both run on the draft tier and never fall back: a failure is
logged and tried again later (a path at most once per process and module).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Final

from tutor.curriculum import paths
from tutor.curriculum.redraft import drain, run
from tutor.relay import hooks
from tutor.relay.protocol import CHAT

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.relay.context import Wiring
    from tutor.relay.curriculum_sync import CurriculumSync

PERIOD_S: Final = 30.0
SWITCH_ENV: Final = "TUTOR_CARD_WORK"
POLL_S: Final = 2.0
FRESH_S: Final = 900.0  # a learner message older than this awaits no reply
_logger = logging.getLogger(__name__)


def reply_in_flight(sessions: Path, now: float) -> bool:
    """Whether the newest transcript ends on a recent learner message.

    The deploy script's rule (``tutor_deploy.sh`` ``wait_idle``), which also
    sees a reply asked for on the desktop page, not only over the relay.
    """
    logs = sorted(sessions.glob("*.jsonl"))
    if not logs or now - logs[-1].stat().st_mtime > FRESH_S:
        return False
    lines = logs[-1].read_text(encoding="utf-8").strip().splitlines()
    try:
        last = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError as err:
        _logger.warning("unreadable last line in %s: %s", logs[-1].name, err)
        return False
    return isinstance(last, dict) and last.get("type") == "learner"


class CardWork:
    """The redraft drain and the path writer of one worker."""

    def __init__(
        self, wiring: Wiring, curriculum: CurriculumSync, current: dict[str, str | None]
    ) -> None:
        """``current``: the lanes' in-flight request ids (``Server.current``)."""
        self.w, self.curriculum, self.current = wiring, curriculum, current
        self._failed: set[tuple[str, str]] = set()

    def busy(self) -> bool:
        """A learner's reply is being written (relay chat lane or the page)."""
        sessions = self.w.engine.store.root / "sessions"
        return self.current[CHAT] is not None or reply_in_flight(sessions, time.time())

    def wait(self) -> None:
        """Block (a drain thread) until no reply is in flight."""
        while self.busy():
            time.sleep(POLL_S)

    async def once(self) -> str:
        """One round; returns what it did (``redraft``, ``paths``, ``idle``)."""
        ctx = self.w.engine.ctx
        if await asyncio.to_thread(run.pending, ctx):
            await asyncio.to_thread(
                drain.drain, ctx, self.wait, drain.WORKERS, drain.WORKERS
            )
            await self.curriculum.sync()
            return "redraft"
        todo = list(await asyncio.to_thread(paths.pending, ctx))
        todo = [p for p in todo if p not in self._failed]
        if not todo or self.busy():
            return "idle"
        subject, module = todo[0]
        try:
            await asyncio.to_thread(paths.write, ctx, subject, module)
        except hooks.BASE_ERRORS as err:
            _logger.warning("paths for %s/%s failed: %s", subject, module, err)
            self._failed.add((subject, module))
        return "paths"

    async def run(self) -> None:
        """Forever: one round every :data:`PERIOD_S`; a failure never ends it.

        ``TUTOR_CARD_WORK=off`` (the E2E sandbox, whose data is a copy) ends
        it at once: no draft-tier call is ever made there.
        """
        if os.environ.get(SWITCH_ENV) == "off":
            return
        while True:
            await asyncio.sleep(PERIOD_S)
            try:
                await self.once()
            except hooks.BASE_ERRORS as err:
                _logger.warning("background card work failed: %s", err)
