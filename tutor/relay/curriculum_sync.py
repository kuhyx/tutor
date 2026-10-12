# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The curriculum over RTDB: event log both ways, the fold, subjects, generation.

``sync`` (before and after every request, and every minute) pulls every other
device's new ``log/{dev}`` events into the local log, re-folds
(``fold_and_advance``), publishes every subject whose local ``rev`` moved,
PATCHes this worker's own ``taught``/``untaught`` events to ``log/{own}``,
and queues card generation. Generation (minutes of model time) runs one
module at a time under the build lane's lock, so it never overlaps a build
request (``DOCS-contract-curriculum.md`` §9).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import handlers as cur
from tutor.curriculum.subject_store import read_json
from tutor.relay.protocol import DEV

if TYPE_CHECKING:
    from tutor.relay.context import Wiring

_PARTS: Final = ("meta", "plan", "cards", "concepts")
_DEFAULTS: Final[dict[str, object]] = {
    "meta": None,
    "plan": None,
    "cards": {},
    "concepts": [],
}
_logger = logging.getLogger(__name__)


class CurriculumSync:
    """Mirror and publish the curriculum for one worker."""

    def __init__(self, wiring: Wiring) -> None:
        """Nothing read yet; :meth:`startup` learns what RTDB already has."""
        self.w = wiring
        self.lock = asyncio.Lock()  # the build lane: requests and generation
        self.queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self._queued: set[tuple[str, str]] = set()
        self._failed: set[tuple[str, str]] = set()  # not retried in this process
        self._syncing = asyncio.Lock()
        self._last: dict[str, str] = {}  # device -> newest eid seen
        self._pushed: set[str] = set()
        self._sent: dict[tuple[str, str], str] = {}  # (subject, part) -> json
        self._revs: dict[str, int] = {}
        self._catalog = 0

    @property
    def ctx(self) -> cur.Context:
        """The engine's curriculum context (data dir, clock, model)."""
        return self.w.engine.ctx

    async def startup(self) -> None:
        """Learn the published revs and own events, then sync once."""
        rtdb = self.w.rtdb
        catalog = await rtdb.get("rev/catalog")
        self._catalog = catalog if isinstance(catalog, int) else 0
        mine = await rtdb.get(f"log/{self.w.worker}", {"shallow": "true"})
        self._pushed = set(mine) if isinstance(mine, dict) else set()
        for subject in self.ctx.subjects.subjects():
            rev = await rtdb.get(f"subjects/{subject}/meta/rev")
            self._revs[subject] = rev if isinstance(rev, int) else -1
        await self.sync()

    async def pull(self) -> int:
        """Mirror every other device's new log events; returns how many."""
        devices = await self.w.rtdb.get("log", {"shallow": "true"})
        fresh = 0
        for dev in sorted(devices) if isinstance(devices, dict) else []:
            if dev == self.w.worker or not DEV.fullmatch(dev):
                continue
            params = {"orderBy": '"$key"'}
            if dev in self._last:
                params["startAt"] = json.dumps(self._last[dev])
            events = await self.w.rtdb.get(f"log/{dev}", params)
            if isinstance(events, dict) and events:
                self._last[dev] = max(events)
                stored = await asyncio.to_thread(self.ctx.log.mirror, dev, events)
                fresh += len(stored)
        return fresh

    async def push(self) -> None:
        """PATCH this worker's own events RTDB does not have yet."""
        own = self.w.worker
        events = await asyncio.to_thread(self.ctx.log.read)
        new = {
            e["eid"]: {k: v for k, v in e.items() if k not in {"dev", "eid"}}
            for e in events
            if e["dev"] == own and e["eid"] not in self._pushed
        }
        if new:
            await self.w.rtdb.patch(f"log/{own}", new)
            self._pushed |= set(new)

    async def publish(self, subject: str) -> bool:
        """Publish ``subject``'s changed parts; False when its rev did not move."""
        where = self.ctx.subjects.dir(subject)
        parts = {p: read_json(where / f"{p}.json", _DEFAULTS[p]) for p in _PARTS}
        meta = parts["meta"]
        rev = meta.get("rev") if isinstance(meta, dict) else None
        if not isinstance(rev, int) or rev <= self._revs.get(subject, -1):
            return False
        for part in ("plan", "cards", "concepts", "meta"):  # meta (rev) last
            text = json.dumps(parts[part], sort_keys=True)
            if self._sent.get((subject, part)) != text:
                await self.w.rtdb.put(f"subjects/{subject}/{part}", parts[part])
                self._sent[(subject, part)] = text
        self._revs[subject] = rev
        return True

    async def sync(self) -> None:
        """Pull, fold, publish moved subjects, push own events, queue generation."""
        async with self._syncing:
            await self._sync()

    async def _sync(self) -> None:
        await self.pull()
        outcome: dict[str, Any] = await asyncio.to_thread(
            cur.fold_and_advance, self.ctx
        )
        published = [s for s in self.ctx.subjects.subjects() if await self.publish(s)]
        if published:
            self._catalog += 1
            await self.w.rtdb.patch("rev", {"catalog": self._catalog})
        await self.push()
        for subject, module in outcome.get("generate", []):
            key = (subject, module)
            if key not in self._queued and key not in self._failed:
                self._queued.add(key)
                self.queue.put_nowait(key)

    async def generate_forever(self) -> None:
        """Generate queued modules' cards, one at a time, under the build lock."""
        while True:
            subject, module = await self.queue.get()
            async with self.lock:
                try:
                    await asyncio.to_thread(cur.generate, self.ctx, subject, module)
                except (cur.RequestError, OSError, RuntimeError) as err:
                    _logger.warning("generating %s/%s failed: %s", subject, module, err)
                    self._failed.add((subject, module))
                finally:
                    self._queued.discard((subject, module))
            await self.sync()
