# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``TUTOR_SYNC_NAMESPACE``: a worker for a phone slot build (``sandbox/slotN``).

A slot APK (``SYNC_NAMESPACE=sandbox/slotN``) reads and writes every RTDB
path under ``/sandbox/slotN/``. The worker must do the same, raw ``at()``
clients included (the e2e header at ``""``, the one-time copy from
``tutor/v1``), or it would serve, and write to, the live tree.
"""

from __future__ import annotations

import asyncio
from typing import Any

import crdt_sync
import pytest

from tutor.relay import config, e2e
from tutor.relay.rtdb import ROOT, Rtdb


@pytest.fixture
def signed_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """``connect()`` finds a config and a session (no network is touched)."""

    class Cfg:
        api_key, database_url = "k", "https://db.test"

    class Provider:
        def __init__(self, api_key: str, store: object) -> None:
            del api_key, store

        def has_session(self) -> bool:
            return True

    monkeypatch.setattr(crdt_sync.FirebaseConfig, "load", Cfg)
    monkeypatch.setattr(config, "FirebaseTokenProvider", Provider)


async def _token() -> str:
    return "t"


@pytest.mark.usefixtures("signed_in")
def test_no_namespace_keeps_the_live_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.NAMESPACE_ENV, raising=False)
    db = config.connect()
    assert db.root == ROOT
    assert db.at("").root == ""
    assert db.at(e2e.OLD_ROOT).root == e2e.OLD_ROOT
    monkeypatch.setenv(config.NAMESPACE_ENV, "")
    assert config.connect().root == ROOT


@pytest.mark.usefixtures("signed_in")
def test_namespace_moves_every_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(config.NAMESPACE_ENV, "sandbox/slot1")
    db = config.connect()
    assert db.root == f"sandbox/slot1/{ROOT}"
    assert db.url("stats").startswith(f"https://db.test/sandbox/slot1/{ROOT}/stats")
    # The raw clients: the e2e header store, the old-root copy, the server's.
    assert db.at("").root == "sandbox/slot1"
    assert db.at(e2e.OLD_ROOT).root == "sandbox/slot1/tutor/v1"
    assert db.at(db.root).root == db.root
    assert db.at("").at("").root == "sandbox/slot1"


@pytest.mark.parametrize(
    "bad", ["tutor", "sandbox/", "sandbox/Slot1", "sandbox/slot1\n", "sandbox/a/b"]
)
@pytest.mark.usefixtures("signed_in")
def test_bad_namespace_fails_closed(monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    monkeypatch.setenv(config.NAMESPACE_ENV, bad)
    with pytest.raises(config.RelaySetupError, match="TUTOR_SYNC_NAMESPACE"):
        config.connect()


def test_migrate_stays_inside_the_namespace() -> None:
    """The one-time copy reads and fences ``<ns>/tutor/v1``, never ``tutor/v1``."""
    touched: list[str] = []

    class Recording(Rtdb):
        async def get(self, path: str, query: Any = None) -> Any:
            touched.append(f"{self.root}/{path}")
            return None

        async def put(self, path: str, value: object) -> None:
            del value
            touched.append(f"{self.root}/{path}")

        async def patch(self, path: str, value: object) -> None:
            del value
            touched.append(f"{self.root}/{path}")

    db = Recording.under("sandbox/slot1", "https://db.test", _token)
    asyncio.run(e2e.migrate(db))
    asyncio.run(db.aclose())
    assert touched
    assert all(p.startswith("sandbox/slot1/") for p in touched), touched
