# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``sessions/{sid}/progress``: the turn's thinking and tool calls, live.

Desktop (the web build) and phone both read RTDB, so one node serves both
(DOCS-contract §6). It is append-only: the first write of a request PUTs
``{"rid", "steps"}``, later ones PATCH ``progress/steps`` with only the new
``s%04d`` keys, so every SSE event carries just what is new. Writes are
throttled per request: at most every :data:`DESKTOP_EVERY` s when the request
came from the desktop, :data:`PHONE_EVERY` s from the phone. The node is
deleted when the request ends (with ``busy``).

The SDK read loop only calls :meth:`TracePublisher.update` (no I/O there);
:meth:`TracePublisher.run` does the writes in the claim's keeper task.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.delivery import PHONE
from tutor.relay.rtdb import RtdbError
from tutor.trace import coalesce

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.relay.rtdb import Rtdb
    from tutor.trace import Trace

DESKTOP_EVERY: Final = 0.5
PHONE_EVERY: Final = 2.0
_logger = logging.getLogger(__name__)


def every_for(body: dict[str, Any]) -> float:
    """The write interval for a request ``body`` (its ``device``)."""
    return PHONE_EVERY if body.get("device") == PHONE else DESKTOP_EVERY


def path(sid: str) -> str:
    """``sessions/{sid}/progress``."""
    return f"sessions/{sid}/progress"


class TracePublisher:
    """Writes one request's trace to its session's ``progress`` node."""

    def __init__(
        self,
        rtdb: Rtdb,
        sid: str,
        rid: str,
        every: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Nothing is written until the first :meth:`update`."""
        self._rtdb, self.sid, self.rid, self.every = rtdb, sid, rid, every
        self._sleep = sleep
        self._trace: Trace | None = None
        self._sent = 0  # chunks of ``_trace`` already written
        self._keys = 0  # step keys used so far (a retry's trace continues)
        self._written = False  # the PUT landed: later writes PATCH steps
        self._touched = False  # a write was sent: clear() must DELETE
        self._dirty = asyncio.Event()

    def update(self, trace: Trace) -> None:
        """The trace grew (a new object: a retry, which starts at its chunk 0)."""
        if trace is not self._trace:
            self._trace, self._sent = trace, 0
        self._dirty.set()

    async def run(self) -> None:
        """Write at once, then at most once per interval; until cancelled."""
        while True:
            await self._dirty.wait()
            self._dirty.clear()
            try:
                await self._flush()
            except RtdbError as err:  # kept pending: the next flush retries
                _logger.warning("progress write failed: %s", err)
                self._dirty.set()
            await self._sleep(self.every)

    async def _flush(self) -> None:
        trace = self._trace
        if trace is None or len(trace.chunks) <= self._sent:
            return
        end = len(trace.chunks)
        fresh = {
            f"s{self._keys + n:04d}": step
            for n, step in enumerate(coalesce(trace.chunks[self._sent : end]), 1)
        }
        if self._written:
            await self._rtdb.patch(f"{path(self.sid)}/steps", fresh)
        else:
            # Marked first: a PUT cancelled in flight may still land.
            self._touched = True
            await self._rtdb.put(path(self.sid), {"rid": self.rid, "steps": fresh})
            self._written = True
        self._sent, self._keys = end, self._keys + len(fresh)

    async def clear(self) -> bool:
        """Delete the node if this request wrote it (False: the delete failed)."""
        if not self._touched:
            return True
        try:
            await self._rtdb.delete(path(self.sid))
        except RtdbError as err:
            _logger.warning("progress clear on %s failed: %s", self.sid, err)
            return False
        self._written = self._touched = False
        return True
