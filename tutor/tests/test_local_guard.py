# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A web page in kuhy's browser must not be able to drive the tutor (Claude)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from tutor.local_guard import LocalGuard
from tutor.server import create_app
from tutor.tests._fakes import BASE_URL, FakeSession, turn
from tutor.tests.test_server import Rig

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from starlette.types import Message, Receive, Scope, Send

JSON = {"content-type": "application/json"}
ORIGIN = {"origin": BASE_URL, **JSON}
EVIL = "http://evil.example"


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path, FakeSession(turn("Begin"), turn("Next")))


@pytest.fixture
def client(rig: Rig) -> Iterator[TestClient]:
    app = create_app(rig.engine, media_dirs=(rig.images, rig.svgs))
    with TestClient(app, base_url=BASE_URL) as c:
        yield c


def _nothing_ran(rig: Rig, client: TestClient) -> None:
    assert rig.fake.prompts == []
    assert client.get("/api/state").json()["session_id"] == ""


@pytest.mark.parametrize("host", ["evil.com", "evil.com:8778", "127.0.0.1:9999", ""])
def test_foreign_host_is_403_on_get_and_post(
    rig: Rig, client: TestClient, host: str
) -> None:
    assert client.get("/api/state", headers={"host": host}).status_code == 403
    assert client.get("/", headers={"host": host}).status_code == 403
    assert client.get("/app/", headers={"host": host}).status_code == 403
    for path in ("/api/start", "/api/message", "/api/stop"):
        response = client.post(
            path, json={"text": "hi"}, headers={"host": host, "origin": BASE_URL}
        )
        assert response.status_code == 403
    _nothing_ran(rig, client)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "[::1]"])
def test_loopback_hosts_of_the_port_are_served(client: TestClient, host: str) -> None:
    ok = client.get("/api/state", headers={"host": f"{host}:8778"})
    assert ok.status_code == 200
    # Without the port the Host is not the bound origin: refused.
    assert client.get("/api/state", headers={"host": host}).status_code == 403


@pytest.mark.parametrize("path", ["/api/start", "/api/message", "/api/stop"])
@pytest.mark.parametrize(
    "ctype",
    ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data", None],
)
def test_non_json_post_is_415_and_claude_never_runs(
    rig: Rig, client: TestClient, path: str, ctype: str | None
) -> None:
    headers = {"content-type": ctype} if ctype else {}
    body = b'{"text": "hi", "card_id": null}'
    response = client.post(path, content=body, headers=headers)
    assert response.status_code == 415
    _nothing_ran(rig, client)


def test_text_plain_with_a_foreign_origin_is_refused(
    rig: Rig, client: TestClient
) -> None:
    # The classic "simple request" CSRF: no preflight, body is still JSON text.
    response = client.post(
        "/api/start",
        content=b"{}",
        headers={"content-type": "text/plain", "origin": EVIL},
    )
    assert response.status_code in {403, 415}
    _nothing_ran(rig, client)


@pytest.mark.parametrize(
    "origin", [EVIL, "null", "http://127.0.0.1:9999", "https://127.0.0.1:8778"]
)
def test_foreign_origin_with_json_is_403(
    rig: Rig, client: TestClient, origin: str
) -> None:
    response = client.post("/api/start", json={}, headers={"origin": origin})
    assert response.status_code == 403
    _nothing_ran(rig, client)


def test_origin_must_match_the_host_it_was_sent_to(client: TestClient) -> None:
    headers = {"host": "localhost:8778", "origin": "http://127.0.0.1:8778"}
    assert client.post("/api/stop", json={}, headers=headers).status_code == 403
    headers["origin"] = "http://localhost:8778"
    assert client.post("/api/stop", json={}, headers=headers).status_code == 200


def test_same_origin_json_works(rig: Rig, client: TestClient) -> None:
    started = client.post("/api/start", json={}, headers=ORIGIN)
    assert started.status_code == 200
    assert rig.fake.prompts
    charset = {"content-type": "Application/JSON; charset=utf-8"}
    assert client.post("/api/stop", content=b"{}", headers=charset).status_code == 200


def test_json_without_origin_works(client: TestClient) -> None:
    # curl and the scripted learner send no Origin.
    assert client.post("/api/start", json={}).status_code == 200


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_every_state_changing_method_is_checked(
    client: TestClient, method: str
) -> None:
    plain = {"content-type": "text/plain"}
    assert client.request(method, "/api/start", headers=plain).status_code == 415
    foreign = {"origin": EVIL, **JSON}
    assert client.request(method, "/api/start", headers=foreign).status_code == 403


def test_the_port_is_the_one_the_app_was_built_for(rig: Rig) -> None:
    app = create_app(rig.engine, port=9123, media_dirs=(rig.images, rig.svgs))
    with TestClient(app, base_url="http://127.0.0.1:9123") as c:
        assert c.get("/api/state").status_code == 200
        assert (
            c.get("/api/state", headers={"host": "127.0.0.1:8778"}).status_code == 403
        )


async def _no_receive() -> Message:
    return {}


def test_non_http_scopes_pass_through() -> None:
    seen: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append("ran")

    async def send(message: Message) -> None:
        seen.append("sent")

    guard = LocalGuard(inner, port=8778)
    asyncio.run(guard({"type": "lifespan"}, _no_receive, send))
    assert seen == ["ran"]


def test_websocket_from_a_foreign_host_is_closed_unanswered() -> None:
    sent: list[Message] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:
        sent.append({"type": "app-ran"})

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {"type": "websocket", "headers": [(b"host", b"evil.com")]}
    asyncio.run(LocalGuard(inner, port=8778)(scope, _no_receive, send))
    assert sent == [{"type": "websocket.close", "code": 1008}]
