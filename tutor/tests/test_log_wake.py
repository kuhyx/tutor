# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A rating written to ``log/`` by another device wakes a sync at once.

``LogWake`` follows ``log/`` by stream; its payload only wakes the worker
(``pull()`` stays the one path into ``log.jsonl``). The first dump is skipped,
a reconnect dump syncs once, the worker's own pushes never wake it, and
events during a sync fold into one follow-up sync.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tutor.relay import log_wake
from tutor.relay.sse import Event, StreamCancelledError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

OWN = "0a11ffcc-c504-464f-8f85-abcb9e993929"
PHONE = "7f3c2b10-1111-4222-8333-944455556666"
DUMP = Event("put", "/", {OWN: {"e1": {}}, PHONE: {"e0": {}}})


class Syncs:
    """A sync that counts its runs; ``gate`` holds a run until released."""

    def __init__(self, *, fail: bool = False) -> None:
        self.runs = 0
        self.fail = fail
        self.gate: asyncio.Event | None = None
        self.entered = asyncio.Event()

    async def __call__(self) -> None:
        self.runs += 1
        self.entered.set()
        if self.gate is not None:
            await self.gate.wait()
        if self.fail:
            msg = "rtdb down"
            raise OSError(msg)


async def settle() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


def test_the_first_dump_is_skipped_and_a_phone_event_syncs() -> None:
    async def run() -> int:
        syncs = Syncs()
        wake = log_wake.LogWake(OWN, syncs)
        drain = asyncio.create_task(wake.drain())
        wake.on_event(DUMP)
        await settle()
        assert syncs.runs == 0
        wake.on_event(Event("patch", f"/{PHONE}", {"e2": {"t": "review"}}))
        await settle()
        drain.cancel()
        return syncs.runs

    assert asyncio.run(run()) == 1


def test_own_pushes_never_wake() -> None:
    wake = log_wake.LogWake(OWN, Syncs())
    wake.on_event(DUMP)
    wake.on_event(Event("patch", f"/{OWN}", {"e3": {}}))
    wake.on_event(Event("put", f"/{OWN}/e4", {}))
    wake.on_event(Event("patch", "/", {f"{OWN}/e5": {}}))
    assert not wake.dirty.is_set()
    wake.on_event(Event("patch", "/", {f"{OWN}/e6": {}, f"{PHONE}/e7": {}}))
    assert wake.dirty.is_set()


def test_a_reconnect_dump_syncs_once() -> None:
    wake = log_wake.LogWake(OWN, Syncs())
    wake.on_event(DUMP)
    assert not wake.dirty.is_set()
    wake.on_event(DUMP)  # the stream reconnected: ratings may be in the gap
    assert wake.dirty.is_set()


def test_events_during_a_sync_fold_into_one_follow_up() -> None:
    async def run() -> int:
        syncs = Syncs()
        syncs.gate = asyncio.Event()
        wake = log_wake.LogWake(OWN, syncs)
        drain = asyncio.create_task(wake.drain())
        wake.on_event(DUMP)
        wake.on_event(Event("put", f"/{PHONE}/e1", {}))
        await syncs.entered.wait()
        for n in range(5):
            wake.on_event(Event("put", f"/{PHONE}/f{n}", {}))
        syncs.gate.set()
        await settle()
        drain.cancel()
        return syncs.runs

    assert asyncio.run(run()) == 2


def test_a_failed_sync_keeps_the_loop_alive() -> None:
    async def run() -> int:
        syncs = Syncs(fail=True)
        wake = log_wake.LogWake(OWN, syncs)
        drain = asyncio.create_task(wake.drain())
        wake.on_event(DUMP)
        wake.on_event(Event("put", f"/{PHONE}/e1", {}))
        await settle()
        wake.on_event(Event("put", f"/{PHONE}/e2", {}))
        await settle()
        assert not drain.done()
        drain.cancel()
        return syncs.runs

    assert asyncio.run(run()) == 2


def test_run_follows_the_stream_and_ends_when_it_is_cancelled() -> None:
    async def stream() -> AsyncIterator[Event]:
        yield DUMP
        yield Event("put", f"/{PHONE}/e1", {})
        await asyncio.sleep(0.01)  # let the drain sync before the cancel
        msg = "rules refuse log/"
        raise StreamCancelledError(msg)

    syncs = Syncs()
    wake = log_wake.LogWake(OWN, syncs)
    with pytest.raises(ExceptionGroup) as caught:
        asyncio.run(wake.run(stream()))
    assert caught.group_contains(StreamCancelledError)
    assert syncs.runs == 1
