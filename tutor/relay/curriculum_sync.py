# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The curriculum over RTDB: event log both ways, the fold, subjects, generation.

``sync`` (before and after every request, every minute, and at once when
another device writes to ``log/``: :mod:`tutor.relay.log_wake`) pulls every other
device's new ``log/{dev}`` events into the local log, re-folds
(``fold_and_advance``), publishes every subject whose local ``rev`` moved,
deletes archived subjects (``curriculum/archive.py``), PATCHes this
worker's own ``taught``/``untaught`` events to ``log/{own}``,
queues card generation, and pays new app-review minutes
(:mod:`tutor.review_credit`; a failure there is logged, never blocks the
rest), today's and yesterday's leftover minutes (:mod:`tutor.leftover`), then
tops up today's carry-over (:mod:`tutor.carry`). Generation
(minutes of model time) runs one module at a time under the build lane's
lock, so it never overlaps a build request (``DOCS-relay.md`` "Curriculum").
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import carry, leftover, outage, review_credit, unavailable
from tutor.credit import local_day
from tutor.curriculum import handlers as cur
from tutor.curriculum import log_order, theory_phase
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE
from tutor.curriculum.subject_store import read_json
from tutor.relay import hooks
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
        # Hit Claude's spent limit: drafted again once the outage window closes.
        self._waiting: set[tuple[str, str]] = set()
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
        for subject in self.ctx.subjects.subjects(archived=True):
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
        # An own event minted below an eid already stored (a backdated
        # writer in another process) is invisible to readers past it:
        # re-mint it above every own eid first (log_order).
        lifted = log_order.copies(events, own, self.ctx.clock())
        if lifted:
            await asyncio.to_thread(self.ctx.log.append, lifted)
            events = [*events, *lifted]
        new = {
            e["eid"]: {k: v for k, v in e.items() if k not in {"dev", "eid"}}
            for e in events
            if e["dev"] == own and e["eid"] not in self._pushed
        }
        if new:
            await self.w.rtdb.patch(f"log/{own}", new)
            self._pushed |= set(new)

    async def publish(self, subject: str) -> bool:
        """Publish ``subject``'s changed parts; False when nothing moved.

        The plan carries C3's ``teachable`` per gated module (``overlay``): at
        an unchanged rev only that can move, and only the plan is re-PUT.
        """
        where = self.ctx.subjects.dir(subject)
        parts = {p: read_json(where / f"{p}.json", _DEFAULTS[p]) for p in _PARTS}
        meta = parts["meta"]
        rev = meta.get("rev") if isinstance(meta, dict) else None
        last = self._revs.get(subject, -1)
        if not isinstance(rev, int) or rev < last:
            return False
        parts["plan"] = theory_phase.overlay(subject, parts["plan"])
        if rev == last:
            return subject in theory_phase.GATED and await self._put(subject, parts)
        for part in ("plan", "cards", "concepts", "meta"):  # meta (rev) last
            await self._put(subject, parts, part)
        self._revs[subject] = rev
        return True

    async def _put(
        self, subject: str, parts: dict[str, object], part: str = "plan"
    ) -> bool:
        """PUT one part unless RTDB already holds it; whether it was sent."""
        text = json.dumps(parts[part], sort_keys=True)
        if self._sent.get((subject, part)) == text:
            return False
        await self.w.rtdb.put(f"subjects/{subject}/{part}", parts[part])
        self._sent[(subject, part)] = text
        return True

    async def _remove(self, subject: str) -> bool:
        """Delete an archived subject's RTDB copy; False when it has none.

        Its caches are dropped, so an unarchive re-PUTs every part.
        """
        if self._revs.get(subject, -1) < 0:
            return False
        await self.w.rtdb.delete(f"subjects/{subject}")
        self._revs[subject] = -1
        for part in _PARTS:
            self._sent.pop((subject, part), None)
        return True

    async def sync(self) -> None:
        """Pull, fold, publish moved subjects, push own events, queue generation.

        A failure is logged and the caller goes on (the next sync retries).
        """
        async with self._syncing:
            try:
                await self._sync()
            except hooks.BASE_ERRORS as err:  # never kills a lane or the timer
                _logger.warning("curriculum sync failed: %s", err)

    async def _sync(self) -> None:
        await self.pull()
        outcome: dict[str, Any] = await asyncio.to_thread(
            cur.fold_and_advance, self.ctx
        )
        published = [s for s in self.ctx.subjects.subjects() if await self.publish(s)]
        removed = [s for s in sorted(self.ctx.archived()) if await self._remove(s)]
        if published or removed:
            self._catalog += 1
            await self.w.rtdb.patch("rev", {"catalog": self._catalog})
        await self.push()
        closed = unavailable.current(self.w.now()) is None
        for subject, module in outcome.get("generate", []):
            key = (subject, module)
            if key in self._waiting and closed:
                self._waiting.discard(key)
            if key not in self._queued | self._failed | self._waiting:
                self._queued.add(key)
                self.queue.put_nowait(key)
        await asyncio.to_thread(review_credit.credit_now, self.ctx, self.w.now())
        # Today's closed cards and yesterday's last one (startup paid the rest).
        now = self.w.now()
        days = [local_day(now - 86400)[0], local_day(now)[0]]
        await asyncio.to_thread(
            leftover.pay,
            self.ctx.data_dir / "sessions",
            now=now,
            days=[d.replace("-", "") for d in days],
        )
        # After them: yesterday's late reviews may have raised today's carry.
        await asyncio.to_thread(carry.spend, now=self.w.now())

    async def generate_forever(self) -> None:
        """Generate queued modules' cards, one at a time, under the build lock."""
        while True:
            subject, module = await self.queue.get()
            async with self.lock:
                try:
                    if subject not in self.ctx.archived():  # not archived since
                        outage.ensure_available(self.w.now())  # no CLI in a window
                        await asyncio.to_thread(cur.generate, self.ctx, subject, module)
                except hooks.BASE_ERRORS as err:
                    _logger.warning("generating %s/%s failed: %s", subject, module, err)
                    spent = _spent(err)
                    (self._waiting if spent else self._failed).add((subject, module))
                finally:
                    self._queued.discard((subject, module))
            await self.sync()


def _spent(err: BaseException) -> bool:
    """True when ``err`` (or its cause) is Claude's spent limit or an outage."""
    seen: BaseException | None = err
    while seen is not None:
        if isinstance(seen, outage.ClaudeUnavailableError):
            return True
        if getattr(seen, "code", None) == CLAUDE_UNAVAILABLE:
            return True
        seen = seen.__cause__
    return False
