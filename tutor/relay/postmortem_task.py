# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker's post-mortem loop: one ``postmortem.watch.tick`` a minute.

Its own task and its own switch (``TUTOR_POSTMORTEM_WORK=off``), apart from
``CardWork``: the E2E sandbox turns card work off yet must run post-mortems
(flow F32). A round waits while a learner's reply is in flight, and after a
post-mortem changed cards it syncs the curriculum, so the phone sees them.
A failure is logged and the loop goes on; the tick never retries a failed
post-mortem itself (its marker stops it).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Final

from tutor.postmortem import watch
from tutor.relay import hooks

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.relay.context import Wiring
    from tutor.relay.curriculum_sync import CurriculumSync

PERIOD_S: Final = 60.0
SWITCH_ENV: Final = "TUTOR_POSTMORTEM_WORK"
_logger = logging.getLogger(__name__)


class PostmortemWork:
    """The post-mortem tick of one worker."""

    def __init__(
        self, wiring: Wiring, curriculum: CurriculumSync, busy: Callable[[], bool]
    ) -> None:
        """``busy``: whether a learner's reply is being written (``CardWork.busy``)."""
        self.w, self.curriculum, self.busy = wiring, curriculum, busy
        self.stopped = False  # set to end :meth:`run` after its current round

    async def once(self) -> str:
        """One round; returns the tick's outcome, or ``busy``."""
        if self.busy():
            return "busy"
        ctx = self.w.engine.ctx
        outcome = await asyncio.to_thread(watch.tick, ctx, time.time())
        if outcome == "done":
            await self.curriculum.sync()
        return outcome

    async def run(self) -> None:
        """Forever, one round every :data:`PERIOD_S`; ``off`` ends it at once."""
        if os.environ.get(SWITCH_ENV) == "off":
            return
        while not self.stopped:
            await asyncio.sleep(PERIOD_S)
            try:
                await self.once()
            except hooks.BASE_ERRORS as err:
                _logger.warning("post-mortem round failed: %s", err)
