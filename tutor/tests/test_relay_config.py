# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The relay's config seam (session, token, device id) and ``python -m tutor``."""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any

import crdt_sync
from crdt_sync import ConfigError, FirebaseAuthError
import pytest
import uvicorn

from tutor import __main__ as tutor_main
from tutor.relay import cli, config
from tutor.relay.phases import PhaseSink
from tutor.relay.rtdb import RtdbError
from tutor.tests._relay_support import engine

if TYPE_CHECKING:
    from pathlib import Path


def test_config_connect_and_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_config() -> Any:
        msg = "missing"
        raise ConfigError(msg)

    monkeypatch.setattr(crdt_sync.FirebaseConfig, "load", no_config)
    with pytest.raises(config.RelaySetupError, match="no crdt-sync firebase config"):
        config.connect()

    class Cfg:
        api_key, database_url = "k", "https://db.test"

    class Provider:
        session = False

        def __init__(self, api_key: str, store: object) -> None:
            assert (api_key, store is not None) == ("k", True)

        def has_session(self) -> bool:
            return Provider.session

        def id_token(self) -> str:
            msg = "revoked"
            raise FirebaseAuthError(msg)

    monkeypatch.setattr(crdt_sync.FirebaseConfig, "load", Cfg)
    monkeypatch.setattr(config, "FirebaseTokenProvider", Provider)
    with pytest.raises(config.RelaySetupError, match="seed_session"):
        config.connect()
    Provider.session = True
    db = config.connect()

    async def go() -> None:
        with pytest.raises(RtdbError, match="firebase auth failed: revoked"):
            await db.get("x")
        await db.aclose()

    asyncio.run(go())
    assert config.device_id(tmp_path) == config.device_id(tmp_path)


def test_main_dispatches_commands_and_relay_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Any] = []

    def fake_main(argv: list[str]) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr(cli, "main", fake_main)
    assert tutor_main.main(["publish-all"]) == 0
    monkeypatch.setattr(sys, "argv", ["tutor", "worker"])
    assert tutor_main.main() == 0
    assert calls == [["publish-all"], ["worker"]]
    eng, _ = engine(tmp_path)
    monkeypatch.setattr(tutor_main, "_port_busy", lambda _port: False)
    monkeypatch.setattr(cli, "relay_engine", lambda simulated_time: (eng, PhaseSink()))
    monkeypatch.setattr(
        cli, "with_relay", lambda app, engine, sink: calls.append(("relay", engine))
    )
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append("served"))
    monkeypatch.setenv("TUTOR_RELAY", "1")
    assert tutor_main.main(["--port", "18999", "--fresh"]) == 0
    assert calls[-2:] == [("relay", eng), "served"]
