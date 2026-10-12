# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``python -m tutor worker`` / ``publish-all``, and the relay inside the server.

* ``worker``: the relay alone, no HTTP (the Flutter-only future).
* ``publish-all``: one-off migration publish of every transcript, plus the
  archived flags, then exit (``DOCS-contract.md`` §11).
* :func:`with_relay`: the web server's lifespan also runs the relay
  (``TUTOR_RELAY=1`` / ``--relay``), so the desktop app and the phone share
  ONE engine.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import signal
import time
from typing import TYPE_CHECKING

from tutor.engine import Engine
from tutor.relay import config, phases
from tutor.relay.context import Wiring
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.done import DoneMap
from tutor.relay.projection import Publisher
from tutor.relay.worker import Relay, running

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from starlette.applications import Starlette

_logger = logging.getLogger(__name__)
COMMANDS = ("worker", "publish-all")


def prepare(engine: Engine, *, fresh: bool = False) -> None:
    """What a starting server does before serving: repair, backfill, resume."""
    for card, sid in engine.repair_done_cards():
        _logger.warning("marked %s done from %s", card, sid)
    engine.backfill_today()
    if not fresh and engine.resume_latest():
        _logger.warning("resumed session %s", engine.session_id)


def relay_engine(*, simulated_time: bool = False) -> tuple[Engine, phases.PhaseSink]:
    """An Engine whose model sessions report their phases to the relay."""
    sink = phases.PhaseSink()
    factory = phases.session_factory(sink)
    return Engine(session_factory=factory, simulated_time=simulated_time), sink


def with_relay(app: Starlette, engine: Engine, sink: phases.PhaseSink) -> None:
    """Run the relay for as long as ``app`` serves (wraps its lifespan)."""
    inner = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(host: Starlette) -> AsyncIterator[None]:
        try:
            rtdb = config.connect()
        except config.RelaySetupError:
            _logger.exception("relay disabled, serving the web app only")
            async with inner(host):
                yield
            return
        async with inner(host), running(Relay(engine, rtdb, sink, time.time)):
            yield

    app.router.lifespan_context = lifespan


async def _worker(stop: asyncio.Event | None = None) -> None:
    engine, sink = relay_engine()
    prepare(engine)
    stop = stop or asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        async with running(Relay(engine, config.connect(), sink, time.time)):
            await stop.wait()
    finally:
        await engine.close()


async def _publish_all() -> None:
    engine = Engine()
    rtdb = config.connect()
    done = DoneMap(engine.store.root / "requests_done.jsonl", time.time())
    publisher = Publisher(rtdb, engine, done)
    try:
        sessions = await publisher.startup(force=True)
        archived = await publisher.archived()
        sink, now = phases.PhaseSink(), time.time
        wiring = Wiring(rtdb, engine, publisher, done, sink, "", now)
        subjects = await publish_subjects(CurriculumSync(wiring))
    finally:
        await rtdb.aclose()
    print(
        f"published {sessions} session(s), {archived} archived flag(s), "
        f"{subjects} subject(s)"
    )


async def publish_subjects(sync: CurriculumSync) -> int:
    """Every subject, and this worker's own log events (migration taught)."""
    sync.w = dataclasses.replace(sync.w, worker=sync.ctx.device)
    count = [await sync.publish(s) for s in sync.ctx.subjects.subjects()].count(True)
    await sync.push()
    return count


def main(argv: list[str], run: Callable[..., object] = asyncio.run) -> int:
    """Dispatch ``worker`` / ``publish-all``."""
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s %(name)s: %(message)s"
    )
    try:
        run(_worker() if argv[0] == "worker" else _publish_all())
    except config.RelaySetupError:
        _logger.exception("tutor %s cannot start", argv[0])
        return 1
    return 0
