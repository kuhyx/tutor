# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The worker's heartbeat and clock-skew check (``DOCS-contract.md`` §5, §7).

Every 30 s the worker PUTs ``presence/workers/{dev}`` with a server-time
``beat``; the PUT's response carries that time resolved, so every beat also
measures the skew between this PC's clock and RTDB's (warned about, at most
hourly, beyond 5 s). Clients judge "PC offline" on their own monotonic clock
from when beats stop arriving, never by comparing ``beat`` to theirs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import TYPE_CHECKING, Any, Final

from tutor.relay.claims import ms
from tutor.relay.rtdb import SERVER_TIME, RtdbError

if TYPE_CHECKING:
    from tutor.relay.context import Wiring

BEAT_S: Final = 30.0
SKEW_WARN_MS: Final = 5000
SKEW_WARN_EVERY_S: Final = 3600.0
VERSION: Final = "1"
_logger = logging.getLogger(__name__)


class Presence:
    """Beats for this worker; ``lanes`` names the rid each lane serves."""

    def __init__(self, wiring: Wiring, lanes: dict[str, str | None]) -> None:
        """Bind the worker; the start time is now."""
        self.w, self.lanes = wiring, lanes
        self.started = ms(wiring.now())
        self.skew_ms = 0
        self._warned_at = float("-inf")

    @property
    def path(self) -> str:
        """``presence/workers/{dev}``."""
        return f"presence/workers/{self.w.worker}"

    def node(self) -> dict[str, Any]:
        """The heartbeat record."""
        return {
            "host": socket.gethostname(),
            "pid": os.getpid(),
            "version": VERSION,
            "started": self.started,
            "beat": SERVER_TIME,
            "lanes": dict(self.lanes),
            "skew_ms": self.skew_ms,
        }

    async def beat(self) -> None:
        """One heartbeat; measures the skew from the resolved server time."""
        sent = self.w.now()
        stored = await self.w.rtdb.put(self.path, self.node())
        back = self.w.now()
        server = stored.get("beat") if isinstance(stored, dict) else None
        if not isinstance(server, int):
            return
        self.skew_ms = server - ms((sent + back) / 2)
        if (
            abs(self.skew_ms) > SKEW_WARN_MS
            and back - self._warned_at > SKEW_WARN_EVERY_S
        ):
            self._warned_at = back
            _logger.warning(
                "PC clock is %d ms off RTDB server time; learner timing uses "
                "server time, tutor timing this clock",
                -self.skew_ms,
            )

    async def run(self) -> None:
        """Beat every 30 s, forever (a failed beat is logged and retried)."""
        while True:
            try:
                await self.beat()
            except RtdbError as err:
                _logger.warning("presence beat failed: %s", err)
            await asyncio.sleep(BEAT_S)

    async def leave(self) -> None:
        """Remove the presence record (clean exit)."""
        await self.w.rtdb.delete(self.path)
