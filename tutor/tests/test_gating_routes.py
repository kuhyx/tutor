# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Gating over HTTP: /api/start refuses a locked card."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tutor.engine import Engine
from tutor.server import create_app
from tutor.store import Store
from tutor.tests._fakes import FakeCredit, FakeSession, ManualClock, turn

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

GATED = "fund-five-languages"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = Engine(
        store=Store(tmp_path / "data"),
        now=ManualClock(),
        credit_fn=FakeCredit(),
        session_factory=lambda _prompt: FakeSession(turn("Hi")),
    )
    with TestClient(create_app(engine)) as c:
        yield c


def test_start_route_refuses_a_locked_card(client: TestClient) -> None:
    response = client.post("/api/start", json={"card_id": GATED})
    assert response.status_code == 502
    assert f"cannot start '{GATED}': locked until lang-" in response.json()["error"]
    assert client.get("/api/state").json()["session_id"] == ""
