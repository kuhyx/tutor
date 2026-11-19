# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Fixtures for the public-hostname tests (registered in the root conftest)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tutor import webapp
from tutor.device_gate import DeviceStore, PairCodes, PublicGate
from tutor.server import create_app
from tutor.tests._fakes import BASE_URL, FakeSession, turn
from tutor.tests._public_support import CREDS, PUBLIC
from tutor.tests.test_server import Rig

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    site = tmp_path / "web"
    site.mkdir()
    (site / "index.html").write_text("<html>tutor page</html>", encoding="utf-8")
    creds = tmp_path / "creds.json"
    creds.write_text(json.dumps(CREDS), encoding="utf-8")
    secret = tmp_path / "pass"
    secret.write_text("hunter2\n", encoding="utf-8")
    monkeypatch.setenv(webapp.WEB_DIR_ENV, str(site))
    monkeypatch.setenv(webapp.CREDENTIALS_ENV, str(creds))
    monkeypatch.setenv(webapp.CRDT_SYNC_FILE_ENV, str(secret))
    return site


@pytest.fixture
def gate(tmp_path: Path, clock: Clock) -> PublicGate:
    return PublicGate(
        DeviceStore(tmp_path / "devices.json"), PairCodes(clock=clock), PUBLIC
    )


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path, FakeSession(turn("Begin"), turn("Next")))


@pytest.fixture
def client(rig: Rig, gate: PublicGate, web: Path) -> Iterator[TestClient]:
    app = create_app(rig.engine, media_dirs=(rig.images, rig.svgs), gate=gate)
    with TestClient(app, base_url=BASE_URL, follow_redirects=False) as c:
        yield c
