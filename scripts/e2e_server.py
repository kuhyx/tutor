#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The agent-E2E server: the real engine + relay against a local RTDB emulator.

Never ``config.connect()``: that reads the real Firebase session. The relay
gets an :class:`~tutor.relay.rtdb.Rtdb` on the emulator (``--db``, loopback
only) with an unsigned emulator token, so nothing here can reach the
real database. Before serving it seeds the empty emulator the way the
migration does (``publish-all``: every transcript, archived flag and
subject), plus every device's log events from the data dir copy and
``prefs.current_subject``, then serves the e2e web build
(``$TUTOR_WEBAPP_DIR``) and the relay in one process, as ``tutor.service``
does. The model's working dir follows ``TUTOR_DATA`` into the sandbox
(``tutor.session.sandbox_dir``).

Run by ``scripts/e2e_sandbox.sh up``; refuses the real data dir and :8778.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from collections import defaultdict
import contextlib
import json
import os
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlsplit

import uvicorn

from tutor.engine import Engine
from tutor.relay import cli, phases
from tutor.relay.context import Wiring
from tutor.relay.curriculum_sync import CurriculumSync
from tutor.relay.done import DoneMap
from tutor.relay.projection import Publisher
from tutor.relay.rtdb import Rtdb
from tutor.relay.worker import Relay, running
from tutor.server import create_app

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from starlette.applications import Starlette

LIVE_PORT: Final = 8778
REAL_DATA: Final = Path.home() / ".local" / "share" / "tutor"
LOOPBACK: Final = frozenset({"127.0.0.1", "localhost"})


def _b64(part: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()


# An unsigned JWT: the emulator streams only for a parseable token, and its
# rules are open, so any uid will do (the app builds the same one).
TOKEN: Final = (
    _b64({"alg": "none", "typ": "JWT"})
    + "."
    + _b64(
        {
            "sub": "e2e",
            "user_id": "e2e",
            "iat": 0,
            "exp": 4102444800,
            "aud": "demo-tutor",
        }
    )
    + "."
)


async def _token() -> str:
    return TOKEN


def emulator(url: str) -> Rtdb:
    """An RTDB client on a loopback emulator; anything else is refused."""
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in LOOPBACK:
        msg = f"--db must be a loopback emulator URL, got {url!r}"
        raise SystemExit(msg)
    return Rtdb(url, _token)


def check_sandbox(data: Path, port: int) -> None:
    """Refuse the live data dir, the live port and a missing device id."""
    if (
        data.resolve() == REAL_DATA.resolve()
        or REAL_DATA.resolve() in data.resolve().parents
    ):
        msg = f"TUTOR_DATA={data} is the real data dir"
        raise SystemExit(msg)
    if port == LIVE_PORT:
        msg = "port 8778 belongs to tutor.service"
        raise SystemExit(msg)
    if not (data / "device_id").is_file():
        msg = f"{data} has no device_id: run scripts/e2e_prepare.py first"
        raise SystemExit(msg)


async def seed(db: str, subject: str | None) -> None:
    """Publish the data dir into the empty emulator (``publish-all`` + log + prefs)."""
    rtdb = emulator(db)
    engine = Engine()
    try:
        done = DoneMap(engine.store.root / "requests_done.jsonl", time.time())
        publisher = Publisher(rtdb, engine, done)
        sessions = await publisher.startup(force=True)
        await publisher.archived()
        wiring = Wiring(
            rtdb, engine, publisher, done, phases.PhaseSink(), "", time.time
        )
        sync = CurriculumSync(wiring)
        subjects = await cli.publish_subjects(sync)
        by_dev: dict[str, dict[str, Any]] = defaultdict(dict)
        for event in sync.ctx.log.read():
            body = {k: v for k, v in event.items() if k not in {"dev", "eid"}}
            by_dev[event["dev"]][event["eid"]] = body
        for dev, events in by_dev.items():
            await rtdb.put(f"log/{dev}", events)
        if subject:
            await rtdb.put("prefs", {"current_subject": subject})
        print(
            f"e2e seed: {sessions} session(s), {subjects} subject(s), "
            f"{sum(map(len, by_dev.values()))} event(s) from {len(by_dev)} device(s)",
            flush=True,
        )
    finally:
        await rtdb.aclose()
        await engine.close()


def serve(db: str, port: int) -> None:
    """The engine, its relay on the emulator and the web app, until killed."""
    engine, sink = cli.relay_engine()
    cli.prepare(engine)
    app: Starlette = create_app(engine)
    inner = app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(host: Starlette) -> AsyncIterator[None]:
        async with inner(host), running(Relay(engine, emulator(db), sink, time.time)):
            yield

    app.router.lifespan_context = lifespan
    print(f"e2e server: http://127.0.0.1:{port}/app/?db={db}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def main() -> int:
    """CLI entry (see the module docstring)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="emulator URL, http://127.0.0.1:N")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--subject", help="prefs.current_subject to seed")
    args = parser.parse_args()
    data = Path(os.environ.get("TUTOR_DATA", REAL_DATA))
    check_sandbox(data, args.port)
    asyncio.run(seed(args.db, args.subject))
    serve(args.db, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
