# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Claiming a request and holding its lease (``DOCS-contract.md`` §4 steps 2-4).

One :class:`Claim` per request is the ONLY writer of ``requests/{rid}/claim``:
it holds the current ETag, so phase changes and lease renewals never race
each other into a 412 of our own making. Phases are mirrored to
``sessions/{sid}/meta/busy`` for the session the request is about, and the
model's thinking and tool calls go to its ``progress`` node
(``live_trace.TracePublisher``, written beside the lease in :meth:`keep`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.relay.rtdb import ConflictError, RtdbError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from tutor.relay.live_trace import TracePublisher
    from tutor.relay.rtdb import Rtdb
    from tutor.trace import Trace

LEASE_S: Final = 300.0
RENEW_S: Final = 60.0
MAX_ATTEMPTS: Final = 3
PHASES: Final = ("claimed", "thinking", "images", "checking_images", "publishing")
_logger = logging.getLogger(__name__)


def ms(t: float) -> int:
    """Unix seconds -> unix ms."""
    return int(t * 1000)


def claimable(claim: object, now: float, own: str = "") -> bool:
    """Null, a lease that ran out, or ``own`` (a dead process of this worker).

    The caller has checked there is no result.
    """
    if not isinstance(claim, dict):
        return True
    lease = claim.get("lease_until")
    mine = bool(own) and claim.get("by") == own
    return mine or not isinstance(lease, (int, float)) or lease < ms(now)


class Claim:
    """A held claim: its attempt number, current phase and ETag."""

    def __init__(
        self, rtdb: Rtdb, rid: str, worker: str, now: Callable[[], float]
    ) -> None:
        """Not yet taken; see :meth:`take`."""
        self._rtdb, self.rid, self._worker, self._now = rtdb, rid, worker, now
        self.attempt = 0
        self.phase = "claimed"
        # The session whose meta shows ``busy``, and the pending learner text.
        self.busy_session = ""
        self.busy_text: str | None = None
        # Where the turn's trace goes (set with ``busy_session``), if anywhere.
        self.progress: TracePublisher | None = None
        self._etag = ""
        self._since = now()
        self._changed = asyncio.Event()

    @property
    def path(self) -> str:
        """``requests/{rid}/claim``."""
        return f"requests/{self.rid}/claim"

    def _node(self) -> dict[str, Any]:
        now = self._now()
        return {
            "by": self._worker,
            "lease_until": ms(now + LEASE_S),
            "attempt": self.attempt,
            "phase": self.phase,
            "at": ms(now),
        }

    async def take(self) -> bool:
        """Claim the request (False: someone else holds it, or lost the race)."""
        current, etag = await self._rtdb.get_etag(self.path)
        if not claimable(current, self._now(), self._worker):
            return False
        before = current.get("attempt", 0) if isinstance(current, dict) else 0
        self.attempt = (before if isinstance(before, int) else 0) + 1
        try:
            _, self._etag = await self._rtdb.put_etag(self.path, self._node(), etag)
        except ConflictError:
            _logger.warning("another worker claimed %s first", self.rid)
            return False
        return True

    def set_phase(self, phase: str) -> None:
        """Move to ``phase``; written (and mirrored to busy) by :meth:`keep`."""
        if phase != self.phase:
            self.phase, self._since = phase, self._now()
            self._changed.set()

    async def _write(self, *, phase_changed: bool) -> None:
        try:
            _, self._etag = await self._rtdb.put_etag(
                self.path, self._node(), self._etag
            )
        except ConflictError:
            # Another worker took over after our lease lapsed; ours still
            # commits locally (the done-map dedupes), so only note it.
            _logger.warning("claim on %s lost to another writer", self.rid)
        if phase_changed and self.busy_session:
            await self._mirror_busy()

    async def _mirror_busy(self) -> None:
        node = {
            "rid": self.rid,
            "phase": self.phase,
            "since": ms(self._since),
            "text": self.busy_text,
        }
        await self._rtdb.patch(f"sessions/{self.busy_session}/meta", {"busy": node})

    def set_trace(self, trace: Trace) -> None:
        """The model's trace grew; written (throttled) by :meth:`keep`."""
        if self.progress is not None:
            self.progress.update(trace)

    async def keep(self) -> None:
        """Renew the lease, publish phases and the trace; until cancelled."""
        if self.progress is None:
            await self._keep_lease()
        else:
            await asyncio.gather(self._keep_lease(), self._keep_trace(self.progress))

    @staticmethod
    async def _keep_trace(progress: TracePublisher) -> None:
        """Write the trace; a bug in it never stops the lease or the reply.

        gather, not try/except: whatever ``run`` raises is returned here (a
        cancel of the keeper still cancels it).
        """
        (failed,) = await asyncio.gather(progress.run(), return_exceptions=True)
        _logger.error("live trace stopped; the reply goes on: %r", failed)

    async def _keep_lease(self) -> None:
        """Renew the lease every minute and publish phase changes."""
        if self.busy_session:
            await self._guarded(self._mirror_busy())
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._changed.wait(), RENEW_S)
            changed = self._changed.is_set()
            self._changed.clear()
            await self._guarded(self._write(phase_changed=changed))

    @staticmethod
    async def _guarded(write: Awaitable[object]) -> None:
        """A failed write is logged; the next renewal tries again."""
        try:
            await write
        except RtdbError as err:
            _logger.warning("claim write failed: %s", err)

    async def clear_busy(self) -> bool:
        """Remove ``busy`` (and ``progress``) of a named session (False: failed).

        Unconditional: a mirror PATCH can land and still fail or be cancelled
        here, and a previous process may have left the flag behind.
        """
        if not self.busy_session:
            return True
        cleared = self.progress is None or await self.progress.clear()
        try:
            await self._rtdb.patch(f"sessions/{self.busy_session}/meta", {"busy": None})
        except RtdbError as err:
            _logger.warning("busy clear on %s failed: %s", self.busy_session, err)
            return False
        return cleared
