# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The relay's lifecycle, the CLI, the server hosting and the config seam."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from tutor.relay import cli, config, feedback_drain, inbox, presence, worker
from tutor.relay.phases import PhaseSink
from tutor.server import create_app
from tutor.tests._fake_rtdb import FakeRtdb
from tutor.tests._fakes import turn
from tutor.tests._relay_support import RIDS, engine, request

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def fast(monkeypatch: pytest.MonkeyPatch) -> None:
    for module, name in (
        (worker, "REFRESH_S"),
        (presence, "BEAT_S"),
        (inbox, "RESCAN_S"),
        (feedback_drain, "POLL_S"),
    ):
        monkeypatch.setattr(module, name, 0.01)
    monkeypatch.setattr(worker, "RETRY_S", (0.01,))
    monkeypatch.setattr(worker, "STATS_EVERY", 2)


async def until(check: Callable[[], object], tries: int = 300) -> None:
    for _ in range(tries):
        if check():
            return
        await asyncio.sleep(0.01)
    raise AssertionError


def test_relay_lifecycle(
    tmp_path: Path, fast: None, caplog: pytest.LogCaptureFixture
) -> None:
    del fast
    eng, _ = engine(tmp_path, turn("Q?"))
    fake = FakeRtdb()
    fake.fail[("PUT", "/meta")] = 503  # startup retries

    async def go() -> None:
        relay = worker.Relay(eng, fake.rtdb(), PhaseSink(), eng.time)
        async with worker.running(relay):
            await asyncio.sleep(0.02)
            fake.fail.clear()
            await relay.ready.wait()
            assert fake.get("tutor/v1/meta") == worker.META
            req = request("session_start", {"subject": None, "card": None})
            fake.set(f"tutor/v1/requests/{RIDS[0]}/req", req)
            fake._notify("put", f"tutor/v1/requests/{RIDS[0]}/req", req)
            await until(lambda: fake.get(f"tutor/v1/requests/{RIDS[0]}/result"))
            await until(lambda: fake.get(f"tutor/v1/presence/workers/{relay.w.worker}"))
            fake.fail[("PUT", "/live")] = 500
            await eng.stop()
            await asyncio.sleep(0.05)  # refresh fails loudly, keeps going
            fake.fail.clear()

            async def boom() -> None:
                msg = "task bug"
                raise RuntimeError(msg)

            relay._spawn(boom(), "boom")
            await asyncio.sleep(0.01)
        assert fake.get("tutor/v1/presence") is None

    with caplog.at_level(logging.WARNING):
        asyncio.run(go())
    assert "relay startup failed" in caplog.text
    assert "projection refresh failed" in caplog.text
    assert "relay task relay-boom died" in caplog.text


def test_stop_waits_for_a_request_in_flight_and_survives_a_failed_leave(
    tmp_path: Path,
) -> None:
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()

    async def go() -> None:
        relay = worker.Relay(eng, fake.rtdb(), PhaseSink(), eng.time)
        relay.server.current["chat"] = RIDS[0]
        relay.ready.set()
        fake.fail[("DELETE", f"/presence/workers/{relay.w.worker}")] = 500
        await relay.stop(grace=0.6)

    asyncio.run(go())


def test_stop_before_ready_skips_presence(tmp_path: Path) -> None:
    eng, _ = engine(tmp_path)

    async def go() -> None:
        fake = FakeRtdb()
        relay = worker.Relay(eng, fake.rtdb(), PhaseSink(), eng.time)
        await relay.stop(grace=0)
        assert fake.log == []

    asyncio.run(go())


def test_cli_publish_all_and_setup_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    eng, _ = engine(tmp_path, turn("Q?"))
    asyncio.run(eng.start())
    eng.store.archive("20200101-000000-abcd")
    fake = FakeRtdb()
    monkeypatch.setattr(config, "connect", fake.rtdb)
    monkeypatch.setattr(cli, "Engine", lambda: eng)
    assert cli.main(["publish-all"]) == 0
    assert "published 1 session(s), 1 archived flag(s)" in capsys.readouterr().out

    def refuse() -> Any:
        msg = "no session"
        raise config.RelaySetupError(msg)

    monkeypatch.setattr(config, "connect", refuse)
    assert cli.main(["publish-all"]) == 1


def test_cli_worker_runs_until_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast: None
) -> None:
    del fast
    real_relay_engine = cli.relay_engine
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    monkeypatch.setattr(config, "connect", fake.rtdb)
    monkeypatch.setattr(cli, "relay_engine", lambda: (eng, PhaseSink()))

    async def go() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(cli._worker(stop))
        await until(lambda: fake.get("tutor/v1/meta") is not None)
        stop.set()
        await task

    asyncio.run(go())
    seen: list[object] = []

    def fake_run(coro: Any) -> None:
        seen.append(coro)
        coro.close()

    assert cli.main(["worker"], run=fake_run) == 0
    assert len(seen) == 1
    built, sink = real_relay_engine(simulated_time=True)
    assert built.simulated is True
    assert isinstance(sink, PhaseSink)


def test_server_hosts_the_relay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fast: None
) -> None:
    del fast
    eng, _ = engine(tmp_path)
    fake = FakeRtdb()
    monkeypatch.setattr(config, "connect", fake.rtdb)
    app = create_app(eng)
    cli.with_relay(app, eng, PhaseSink())
    with TestClient(app) as client:
        assert client.get("/api/state").status_code == 200
    assert fake.get("tutor/v1/meta") == worker.META

    def refuse() -> Any:
        msg = "no session"
        raise config.RelaySetupError(msg)

    monkeypatch.setattr(config, "connect", refuse)
    app = create_app(eng)
    cli.with_relay(app, eng, PhaseSink())
    with TestClient(app) as client:
        assert client.get("/api/state").status_code == 200
