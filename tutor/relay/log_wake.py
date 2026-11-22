# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Wake a curriculum sync the moment another device writes to ``log/``.

A review rated on the phone, in Home's queue or in a run left early lands in
``log/{dev}``; the 60 s refresh tick used to be the only thing that pulled
it, so ``review_due.json`` (the LeetCode lock's review row) lagged up to a
minute. The worker now follows ``log/`` by stream, and the stream only wakes
it: ``CurriculumSync.pull`` keeps its ``startAt`` cursor and stays the single
path into ``log.jsonl``, so a payload is never trusted or parsed.

* The first ``put`` at ``/`` is the initial dump: startup synced already.
  A later one is a reconnect: one sync, for ratings made during the gap.
* An event under ``/{own}`` is the worker's own ``push`` echoing back; it
  never wakes, or every sync would set off the next.
* Coalesced: the first event starts a sync at once, everything that arrives
  during it folds into one follow-up sync (a dirty flag, never a queue).

The 60 s tick stays as the fallback (a stream the rules refuse ends this
task, logged by the worker's ``_report``).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tutor.relay import hooks

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from tutor.relay.sse import Event

_logger = logging.getLogger(__name__)


class LogWake:
    """Turn ``log/`` stream events into coalesced syncs."""

    def __init__(self, own: str, sync: Callable[[], Awaitable[None]]) -> None:
        """``own``: this worker's device id; ``sync``: ``CurriculumSync.sync``."""
        self.own = own
        self._sync = sync
        self.dirty = asyncio.Event()
        self._dumped = False

    def _foreign(self, event: Event) -> bool:
        """Whether ``event`` may carry another device's new log event."""
        path = event.path.strip("/")
        if path:
            return path.split("/", 1)[0] != self.own
        if event.kind == "put":  # a (re)connect dump of the whole node
            first, self._dumped = not self._dumped, True
            return not first
        keys = event.data if isinstance(event.data, dict) else {}
        return any(str(k).split("/", 1)[0] != self.own for k in keys)

    def on_event(self, event: Event) -> None:
        """Mark a sync due when ``event`` is another device's."""
        if self._foreign(event):
            self.dirty.set()

    async def drain(self) -> None:
        """Sync whenever marked due; marks during a sync make one more."""
        while True:
            await self.dirty.wait()
            self.dirty.clear()
            try:
                await self._sync()
            except hooks.BASE_ERRORS as err:  # sync logs its own; never die here
                _logger.warning("log wake: sync failed: %s", err)

    async def run(self, events: AsyncIterable[Event]) -> None:
        """Follow ``events`` (``sse.listen(rtdb, "log")``) and drain, forever."""

        async def follow() -> None:
            async for event in events:
                self.on_event(event)

        async with asyncio.TaskGroup() as group:
            group.create_task(follow())
            group.create_task(self.drain())
