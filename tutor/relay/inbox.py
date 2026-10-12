# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Watching ``requests/``: which rid goes to which lane, and garbage collection.

The stream mirrors the whole (small, GC'd) ``requests`` node, our own claim
and result writes included; only a ``req`` with no ``result`` and no live
lease is queued. A lease held by THIS worker's device id but not in flight
here is a dead process's (one worker per device), so it is taken over at
once instead of after the 300 s lease. Every minute the node is rescanned,
which catches leases that ran out and results older than a day (deleted).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.relay import mirror, sse
from tutor.relay.claims import claimable, ms
from tutor.relay.protocol import BUILD, CHAT, KINDS, valid_rid
from tutor.relay.rtdb import RtdbError

if TYPE_CHECKING:
    from tutor.relay.context import Wiring
    from tutor.relay.lanes import Server
    from tutor.relay.sse import Event

GC_AFTER_MS: Final = 24 * 3600 * 1000
RESCAN_S: Final = 60.0
_logger = logging.getLogger(__name__)


def _lane(node: dict[str, Any]) -> str:
    req = node.get("req")
    kind = req.get("kind") if isinstance(req, dict) else None
    return KINDS[kind][0] if isinstance(kind, str) and kind in KINDS else CHAT


class Inbox:
    """The mirrored ``requests`` node and the two lane queues."""

    def __init__(self, wiring: Wiring, server: Server) -> None:
        """Nothing mirrored yet."""
        self.w, self.server = wiring, server
        self.tree: dict[str, Any] = {}
        self.queued: set[str] = set()
        self.queues: dict[str, asyncio.Queue[str]] = {
            CHAT: asyncio.Queue(),
            BUILD: asyncio.Queue(),
        }
        self.draining = False
        self._ignored: set[str] = set()
        self._stale: list[str] = []

    def _wanted(self, node: dict[str, Any], now: float) -> bool:
        if "req" not in node or node.get("result") is not None:
            return False
        return claimable(node.get("claim"), now, self.w.worker)

    def _old(self, node: dict[str, Any], now: float) -> bool:
        result = node.get("result")
        at = result.get("at") if isinstance(result, dict) else None
        return isinstance(at, int) and at < ms(now) - GC_AFTER_MS

    def scan(self) -> None:
        """Queue every servable rid in key order; note results to collect."""
        now = self.w.now()
        for rid, node in sorted(self.tree.items()):
            if rid in self.queued or rid in self._ignored or not isinstance(node, dict):
                continue
            if not valid_rid(rid):
                _logger.warning("request key %r is not a ULID; ignored", rid[:40])
                self._ignored.add(rid)
            elif self._old(node, now):
                self._ignored.add(rid)
                self._stale.append(rid)
            elif not self.draining and self._wanted(node, now):
                self.queued.add(rid)
                self.queues[_lane(node)].put_nowait(rid)

    def on_event(self, event: Event) -> None:
        """Mirror one stream event, then rescan."""
        self.tree = mirror.apply(self.tree, event)
        self.scan()

    async def watch(self) -> None:
        """Follow ``requests`` forever."""
        async for event in sse.listen(self.w.rtdb, "requests"):
            self.on_event(event)

    async def collect(self) -> None:
        """Delete requests whose result is over a day old (the done-map remembers)."""
        while self._stale:
            rid = self._stale.pop()
            try:
                await self.w.rtdb.delete(f"requests/{rid}")
            except RtdbError as err:
                _logger.warning("could not collect request %s: %s", rid, err)
                self._ignored.discard(rid)

    async def tick(self) -> None:
        """Rescan and collect every minute (expired leases, old results)."""
        while True:
            await asyncio.sleep(RESCAN_S)
            self.scan()
            await self.collect()

    async def lane(self, name: str) -> None:
        """Serve the ``name`` lane's queue, one request at a time, forever."""
        queue = self.queues[name]
        while True:
            rid = await queue.get()
            node = self.tree.get(rid)
            try:
                if isinstance(node, dict) and not self.draining:
                    result = await self.server.serve(rid, node.get("req"), name)
                    if result is not None and isinstance(self.tree.get(rid), dict):
                        self.tree[rid]["result"] = {**result, "at": ms(self.w.now())}
            except (RtdbError, OSError) as err:
                _logger.warning(
                    "request %s not served (retried on rescan): %s", rid, err
                )
            finally:
                self.queued.discard(rid)

    def idle(self) -> bool:
        """No request in flight in either lane."""
        return not any(self.server.current.values())
