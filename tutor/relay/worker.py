# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The relay's tasks around one Engine: start, run, drain, stop.

Hosted either inside the web server's process (``hosting``) or alone
(``python -m tutor worker``); in both there is exactly one Engine. Startup
never fails the host: if RTDB is unreachable it keeps retrying in the
background while the web page works on.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Final

from tutor.relay import feedback_drain
from tutor.relay.config import device_id
from tutor.relay.context import Wiring
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.done import DoneMap
from tutor.relay.inbox import Inbox
from tutor.relay.lanes import Server
from tutor.relay.presence import Presence
from tutor.relay.projection import Publisher
from tutor.relay.protocol import BUILD, CHAT
from tutor.relay.rtdb import RtdbError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine

    from tutor.engine import Engine
    from tutor.relay.phases import PhaseSink
    from tutor.relay.rtdb import Rtdb

META: Final = {"schema": 1, "min_client": 1}
REFRESH_S: Final = 30.0
STATS_EVERY: Final = 10  # refreshes (5 min)
CURRICULUM_EVERY: Final = 2  # refreshes (1 min)
RETRY_S: Final = (5.0, 15.0, 60.0)
DRAIN_S: Final = 80.0  # inside systemd's 90 s stop timeout
_logger = logging.getLogger(__name__)


class Relay:
    """Every relay task for one engine; :meth:`start` returns at once."""

    def __init__(
        self, engine: Engine, rtdb: Rtdb, sink: PhaseSink, now: Callable[[], float]
    ) -> None:
        """Wire the parts; nothing touches the network yet."""
        root = engine.store.root
        done = DoneMap(root / "requests_done.jsonl", now())
        publisher = Publisher(rtdb, engine, done)
        self.w = Wiring(rtdb, engine, publisher, done, sink, device_id(root), now)
        self.curriculum = CurriculumSync(self.w)
        self.server = Server(self.w, self.curriculum)
        self.inbox = Inbox(self.w, self.server)
        self.presence = Presence(self.w, self.server.current)
        self.ready = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def _spawn(self, coro: Coroutine[object, object, None], name: str) -> None:
        task = asyncio.create_task(coro, name=f"relay-{name}")
        task.add_done_callback(_report)
        self._tasks.append(task)

    async def _startup(self) -> None:
        """Announce the schema and re-publish stale sessions, retrying until done."""
        attempt = 0
        while True:
            try:
                await self.w.rtdb.put("meta", META)
                count = await self.w.publisher.startup()
                await self.curriculum.startup()
            except RtdbError as err:
                delay = RETRY_S[min(attempt, len(RETRY_S) - 1)]
                attempt += 1
                _logger.warning("relay startup failed (%s); retry in %.0fs", err, delay)
                await asyncio.sleep(delay)
                continue
            _logger.warning(
                "relay up as worker %s; %d session(s) re-published",
                self.w.worker,
                count,
            )
            return

    async def _main(self) -> None:
        await self._startup()
        self._spawn(self.presence.run(), "presence")
        self._spawn(self.inbox.watch(), "watch")
        self._spawn(self.inbox.tick(), "tick")
        self._spawn(self.inbox.lane(CHAT), "chat")
        self._spawn(self.inbox.lane(BUILD), "build")
        self._spawn(feedback_drain.run(self.w), "feedback")
        self._spawn(self._refresh(), "refresh")
        self._spawn(self.curriculum.generate_forever(), "generate")
        self.ready.set()

    async def _refresh(self) -> None:
        """Pick up web-page turns and stats changes the relay did not cause."""
        rounds = 0
        while True:
            await asyncio.sleep(REFRESH_S)
            rounds += 1
            try:
                await self.w.publisher.refresh()
                if rounds % CURRICULUM_EVERY == 0:
                    await self.curriculum.sync()
                if rounds % STATS_EVERY == 0:
                    await self.w.publisher.stats()
            except RtdbError as err:
                _logger.warning("projection refresh failed: %s", err)

    def start(self) -> None:
        """Begin (startup retries in the background)."""
        self._spawn(self._main(), "main")

    async def stop(self, grace: float = DRAIN_S) -> None:
        """Claim nothing new, let a request in flight finish, then leave."""
        self.inbox.draining = True
        waited = 0.0
        while not self.inbox.idle() and waited < grace:
            await asyncio.sleep(0.5)
            waited += 0.5
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self.ready.is_set():
            try:
                await self.presence.leave()
            except RtdbError as err:
                _logger.warning("could not remove presence: %s", err)
        await self.w.rtdb.aclose()


def _report(task: asyncio.Task[None]) -> None:
    """A relay task that died (not cancelled) is logged loudly."""
    if task.cancelled():
        return
    if (err := task.exception()) is not None:
        _logger.error("relay task %s died", task.get_name(), exc_info=err)


@contextlib.asynccontextmanager
async def running(relay: Relay) -> AsyncIterator[Relay]:
    """Run ``relay`` for the duration of the block."""
    relay.start()
    try:
        yield relay
    finally:
        await relay.stop()
