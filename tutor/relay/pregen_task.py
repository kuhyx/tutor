# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker's pre-draft loop: one ``pregen_auto.queue`` round a minute.

A round is skipped while a learner's reply is in flight (``CardWork.busy``)
and while a recorded outage window covers now (``unavailable.current``, the
window ``outage.ensure_available`` refuses on), so read mode's stock is only
drafted while Claude is up. What it queues is
marked ``generating`` + ``pregenerated``; the curriculum sync that follows
hands it to ``generate_forever`` on the build lane, one module at a time.
``TUTOR_CARD_WORK=off`` (the E2E sandbox) turns it off with the rest of the
background card work. A failure is logged and the loop goes on.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Final

from tutor import unavailable
from tutor.curriculum import pregen_auto
from tutor.relay import hooks
from tutor.relay.redraft_task import SWITCH_ENV

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.relay.context import Wiring
    from tutor.relay.curriculum_sync import CurriculumSync

PERIOD_S: Final = 60.0
_logger = logging.getLogger(__name__)


class PregenWork:
    """The automatic pre-draft round of one worker."""

    def __init__(
        self, wiring: Wiring, curriculum: CurriculumSync, busy: Callable[[], bool]
    ) -> None:
        """``busy``: whether a learner's reply is being written (``CardWork.busy``)."""
        self.w, self.curriculum, self.busy = wiring, curriculum, busy
        self.stopped = False  # set to end :meth:`run` after its current round

    async def once(self) -> str:
        """One round: ``busy``, ``unavailable``, ``queued`` or ``idle``."""
        if self.busy():
            return "busy"
        now = self.w.now()
        if unavailable.current(now) is not None:  # what outage.ensure_available reads
            return "unavailable"
        ctx = self.w.engine.ctx
        queued = await asyncio.to_thread(pregen_auto.queue, ctx, int(now * 1000))
        if not queued:
            return "idle"
        _logger.info("pre-drafting %s", queued)
        await self.curriculum.sync()  # queues them for generate_forever
        return "queued"

    async def run(self) -> None:
        """Forever, one round every :data:`PERIOD_S`; ``off`` ends it at once."""
        if os.environ.get(SWITCH_ENV) != "off":
            while not self.stopped:
                await asyncio.sleep(PERIOD_S)
                await self._guarded()

    async def _guarded(self) -> None:
        """:meth:`once`, its failure logged (the next round tries again)."""
        try:
            await self.once()
        except hooks.BASE_ERRORS as err:
            _logger.warning("pre-draft round failed: %s", err)
