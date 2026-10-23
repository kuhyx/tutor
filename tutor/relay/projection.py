# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Publishing the read-only projection: sessions, history rows, live, stats.

Every write here follows a local commit and is idempotent, so a crash
between the two is healed by re-publishing whatever RTDB holds at a lower
``rev`` than the transcript (:meth:`Publisher.startup`). Messages are
append-only: after the first full write only new ``m%04d`` keys are PATCHed,
so a streaming client downloads each message once.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from tutor import carry, history
from tutor.curriculum import handlers as cur
from tutor.relay import commons_url, views
from tutor.relay.claims import ms

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tutor.engine import Engine
    from tutor.relay.done import DoneMap
    from tutor.relay.rtdb import Rtdb

_logger = logging.getLogger(__name__)


class Publisher:
    """Sole writer of sessions (but `user`), session_index, live and stats."""

    def __init__(
        self,
        rtdb: Rtdb,
        engine: Engine,
        done: DoneMap,
        resolve_url: Callable[[str], str | None] = commons_url.resolve,
    ) -> None:
        """Bind the database, the engine whose data dir is published, the done-map."""
        self._rtdb, self._engine, self._done = rtdb, engine, done
        self._resolve = resolve_url
        self._lock = asyncio.Lock()
        self._msgs: dict[str, int] = {}  # sid -> messages already in RTDB
        self._revs: dict[str, int] = {}  # sid -> rev published
        self._live: dict[str, Any] | None = None
        self._live_known = False
        self._stats: dict[str, Any] | None = None
        self._stats_rev = 0

    @property
    def sessions_dir(self) -> Path:
        """The engine's transcripts."""
        return self._engine.store.root / "sessions"

    def _sources(self) -> views.Sources:
        eng = self._engine
        view = history.View(
            fronts={c.id: c.front for c in eng.deck},
            live=eng.session_id,
            done_now=set(eng.store.progress()["cards_done"]),
            archived=set(eng.store.archived()),
        )
        return views.Sources(view, eng.time(), self._done.dev_of, self._resolve)

    async def session(self, sid: str, *, full: bool = False) -> None:
        """Publish session ``sid`` (``full``: rewrite every message)."""
        async with self._lock:
            await self._session(sid, full=full)

    async def _session(self, sid: str, *, full: bool) -> None:
        doc = await asyncio.to_thread(
            views.build, self.sessions_dir, sid, self._sources()
        )
        if doc is None:
            return
        base = f"sessions/{sid}"
        await self._rtdb.patch(f"{base}/meta", doc.meta)
        had = self._msgs.get(sid)
        if full or had is None or had > len(doc.msgs):
            await self._rtdb.put(f"{base}/msgs", doc.msgs)
        elif fresh := dict(list(doc.msgs.items())[had:]):
            await self._rtdb.patch(f"{base}/msgs", fresh)
        await self._rtdb.put(f"{base}/receipts", doc.receipts or None)
        await self._rtdb.put(f"session_index/{sid}", doc.index)
        self._msgs[sid], self._revs[sid] = len(doc.msgs), doc.rev

    def _live_node(self) -> dict[str, Any] | None:
        eng = self._engine
        if not eng.session_id or eng.card is None:
            return None
        since = (self._live or {}).get("since")
        if (self._live or {}).get("session") != eng.session_id:
            since = ms(eng.time())
        return {
            "session": eng.session_id,
            "subject": eng.source.subject,
            "card": eng.card.id,
            "since": since,
        }

    async def live(self) -> None:
        """Publish ``live`` when it changed."""
        node = self._live_node()
        if self._live_known and node == self._live:
            return
        await self._rtdb.put("live", node)
        self._live, self._live_known = node, True

    async def stats(self) -> None:
        """Publish ``stats`` (and bump ``rev.stats``) when it changed."""
        # Today's carry-over first, so the node shows it (DOCS-contract-carry.md).
        # The node's own clock, so the spend and the node agree on "today".
        now = self._engine.ctx.clock() / 1000
        await asyncio.to_thread(carry.spend, now=now)
        node = await asyncio.to_thread(cur.stats, self._engine.ctx)
        if node == self._stats:
            return
        await self._rtdb.put("stats", node)
        self._stats_rev += 1
        await self._rtdb.patch("rev", {"stats": self._stats_rev})
        self._stats = node

    async def after(self, sids: set[str]) -> None:
        """Everything a finished request may have changed."""
        for sid in sorted(s for s in sids if s):
            await self.session(sid)
        await self.live()
        await self.stats()

    async def refresh(self) -> None:
        """Catch changes made outside the relay (HTTP turns) to the live session."""
        sid = self._engine.session_id
        if sid and views.transcript_rev(self.sessions_dir, sid) != self._revs.get(sid):
            await self.session(sid)
        await self.live()

    async def startup(self, *, force: bool = False) -> int:
        """Re-publish every session RTDB holds at a lower rev; returns how many."""
        rows = await self._rtdb.get("session_index") or {}
        rev = await self._rtdb.get("rev/stats")
        self._stats_rev = rev if isinstance(rev, int) else 0
        count = 0
        for path in sorted(self.sessions_dir.glob("*.jsonl")):
            sid = path.stem
            if not history.SESSION_ID.fullmatch(sid):
                continue
            row = rows.get(sid) if isinstance(rows, dict) else None
            remote = row.get("rev") if isinstance(row, dict) else 0
            remote = remote if isinstance(remote, int) else 0
            if force or remote < views.transcript_rev(self.sessions_dir, sid):
                await self.session(sid, full=True)
                count += 1
            else:
                self._revs[sid] = remote
        await self.live()
        await self.stats()
        return count

    async def archived(self) -> int:
        """Migration: progress.json's archived sessions -> ``sessions/{sid}/user``."""
        sids = [
            s for s in self._engine.store.archived() if history.SESSION_ID.fullmatch(s)
        ]
        for sid in sids:
            await self._rtdb.patch(f"sessions/{sid}/user", {"archived": True})
        return len(sids)
