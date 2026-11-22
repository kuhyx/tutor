# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""How fast another device's review reaches this PC, measured on the PC clock.

Run by ``scripts/review_due_watch.py`` as a ``systemd-run --user`` unit that
stops itself after 30 min. It follows ``log/`` read-only with the worker's
RTDB config (its own stream, never the worker's). For each event another
device writes, it notes the PC time the stream delivered it and the PC time
its eid appears in the local ``log.jsonl``; it also notes every change of
``review_due.json``'s mtime. Both times come from this PC, so the phone's
clock skew never enters a delay. Rows go to
``~/.local/state/tutor/review_due_watch.jsonl``; the data dir is only read.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import review_due
from tutor.relay import config, sse
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable

    from tutor.relay.sse import Event

POLL_S: Final = 0.1
RUN_S: Final = 1800.0


def foreign_eids(event: Event, own: str) -> list[tuple[str, str]]:
    """``(dev, eid)`` of each log event in ``event`` that ``own`` did not write.

    A put at ``/`` (the dump on connect) holds old events: none are new.
    """
    path = event.path.strip("/")
    data = event.data if isinstance(event.data, dict) else {}
    if not path and event.kind == "put":
        return []
    found: list[tuple[str, str]] = []
    if path:  # under log/{dev}: one event, or a patch of several
        dev, _, eid = path.partition("/")
        found = [(dev, eid.split("/", 1)[0])] if eid else [(dev, str(e)) for e in data]
    for key, value in data.items() if not path else ():
        # A multi-path patch at the root: {"dev/eid": event} or {"dev": {eid: ...}}.
        dev, _, eid = str(key).partition("/")
        if eid:
            found.append((dev, eid.split("/", 1)[0]))
        elif isinstance(value, dict):
            found += [(dev, str(e)) for e in value]
    return [(dev, eid) for dev, eid in found if dev != own]


def _mtime(path: Path) -> float | None:
    """``path``'s mtime, or None before the worker first writes it."""
    return path.stat().st_mtime if path.exists() else None


@dataclass
class Tracker:
    """Pending eids by arrival time; ``poll`` turns landed ones into rows."""

    own: str
    log: Path
    due: Path
    out: Path
    pending: dict[str, tuple[str, float]] = field(default_factory=dict)
    _log_at: float | None = None
    _due_at: float | None = None

    def __post_init__(self) -> None:
        """Start from the files as they are now."""
        self._due_at = _mtime(self.due)

    def arrived(self, pairs: list[tuple[str, str]], now: float) -> None:
        """Note when the stream delivered each ``(dev, eid)``."""
        for dev, eid in pairs:
            self.pending.setdefault(eid, (dev, now))

    def poll(self, now: float) -> list[dict[str, Any]]:
        """Rows for eids now in ``log.jsonl`` and a moved ``review_due.json``."""
        rows: list[dict[str, Any]] = []
        due_at = _mtime(self.due)
        if due_at != self._due_at:
            self._due_at = due_at
            rows.append({"kind": "review_due", "seen": now, "mtime": due_at})
        log_at = _mtime(self.log)
        if self.pending and log_at is not None and log_at != self._log_at:
            self._log_at = log_at
            text = self.log.read_text(encoding="utf-8")
            for eid in [e for e in self.pending if f'"{e}"' in text]:
                dev, arrived = self.pending.pop(eid)
                rows.append(
                    {"kind": "landed", "eid": eid, "dev": dev, "arrived": arrived}
                    | {"landed": now, "delay_s": round(now - arrived, 3)}
                )
        return rows


async def watch(
    events: AsyncIterable[Event],
    tracker: Tracker,
    *,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    run_s: float = RUN_S,
) -> None:
    """Record arrivals from ``events`` and landings, for ``run_s`` seconds."""
    end = clock() + run_s

    async def follow() -> None:
        async for event in events:
            tracker.arrived(foreign_eids(event, tracker.own), clock())

    task = asyncio.create_task(follow())
    try:
        while clock() < end and not task.done():
            rows = tracker.poll(clock())
            if rows:
                with tracker.out.open("a", encoding="utf-8") as log:
                    log.writelines(json.dumps(r) + "\n" for r in rows)
            await sleep(POLL_S)
    finally:
        task.cancel()


def out_path() -> Path:
    """``~/.local/state/tutor/review_due_watch.jsonl`` (``XDG_STATE_HOME`` honoured)."""
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "tutor" / "review_due_watch.jsonl"


async def main_async(run_s: float = RUN_S) -> None:
    """Watch the live data dir's ``log/`` with the worker's config."""
    data = data_dir()
    out = out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    rtdb = await config.connect_sealed()
    own = config.device_id(data)
    tracker = Tracker(own, data / "log.jsonl", data / review_due.FILE, out)
    try:
        await watch(sse.listen(rtdb, "log"), tracker, run_s=run_s)
    finally:
        await rtdb.aclose()


def main() -> int:
    """CLI entry (``scripts/review_due_watch.py``)."""
    asyncio.run(main_async())
    return 0
