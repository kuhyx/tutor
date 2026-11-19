# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A request on the public hostname reaches the page only when paired (DOCS-public.md)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tutor.device_gate import COOKIE
from tutor.server import create_app
from tutor.tests._fakes import BASE_URL
from tutor.tests._public_support import CREDS, JSON, PUBLIC, pair, pub

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.tests.test_server import Rig


@pytest.mark.parametrize("path", ["/", "/app/", "/api/state", "/media/x.png", "/nope"])
def test_unpaired_public_requests_are_401(client: TestClient, path: str) -> None:
    assert client.get(path, headers=pub()).status_code == 401
    assert client.head(path, headers=pub()).status_code == 401


def test_unpaired_public_post_is_401_and_claude_never_runs(
    rig: Rig, client: TestClient
) -> None:
    for path in ("/api/start", "/api/message", "/api/stop", "/api/pair"):
        reply = client.post(path, json={"text": "hi"}, headers=pub(**JSON))
        assert reply.status_code == 401
    assert rig.fake.prompts == []
    assert client.get("/api/state").json()["session_id"] == ""


@pytest.mark.parametrize(
    "cookie",
    [f"{COOKIE}=forged", f"{COOKIE}=", f"{COOKIE}={'x' * 500}", "other=1", "junk"],
)
def test_a_cookie_that_was_never_issued_is_401(client: TestClient, cookie: str) -> None:
    assert client.get("/app/", headers=pub(cookie)).status_code == 401


def test_local_page_needs_no_cookie(client: TestClient) -> None:
    assert client.get("/app/").status_code == 200
    assert client.get("/api/state").status_code == 200


def test_a_paired_phone_reaches_the_page_and_nothing_else(
    rig: Rig, client: TestClient
) -> None:
    cookie = pair(client)
    for path in ("/api/state", "/media/x.png", "/nope", "/pair/x", "/appx"):
        assert client.get(path, headers=pub(cookie)).status_code == 403
    for path in ("/api/start", "/api/message", "/api/stop"):
        reply = client.post(path, json={"text": "hi"}, headers=pub(cookie, **JSON))
        assert reply.status_code == 403
    assert rig.fake.prompts == []


def test_public_host_is_matched_exactly_and_case_blind(client: TestClient) -> None:
    cookie = pair(client)
    assert (
        client.get("/app/", headers=pub(cookie, host="TUTOR.test")).status_code == 200
    )
    for host in (f"{PUBLIC}:8778", f"x.{PUBLIC}", "evil.com", ""):
        assert client.get("/app/", headers=pub(cookie, host=host)).status_code == 403


def test_a_stuffed_cookie_header_still_needs_one_real_token(
    client: TestClient,
) -> None:
    cookie = pair(client)
    stuffed = f"{COOKIE}=forged; {cookie}"
    assert client.get("/app/", headers=pub(stuffed)).status_code == 200


def test_a_paired_phone_gets_the_sign_in_without_using_up_the_desktops(
    client: TestClient,
) -> None:
    cookie = pair(client)
    site = {"sec-fetch-site": "same-origin"}
    for _ in range(2):
        got = client.get("/app/sync-credentials", headers=pub(cookie, **site))
        assert got.status_code == 200
        assert got.json() == CREDS
        assert got.headers["cache-control"] == "no-store"
    secret = client.get("/app/sync-passphrase", headers=pub(cookie, **site))
    assert secret.json() == {"passphrase": "hunter2"}
    cross = client.get(
        "/app/sync-credentials",
        headers=pub(cookie, **{"sec-fetch-site": "cross-site"}),
    )
    assert cross.status_code == 404
    # The desktop's one serve is untouched.
    assert client.get("/app/sync-credentials").status_code == 200
    assert client.get("/app/sync-credentials").status_code == 404


def test_the_sign_in_is_never_served_unpaired(client: TestClient) -> None:
    for path in ("/app/sync-credentials", "/app/sync-passphrase"):
        assert client.get(path, headers=pub()).status_code == 401
    # ...and the unpaired probe did not burn the desktop's serve.
    assert client.get("/app/sync-credentials").status_code == 200


def test_public_websockets_are_refused(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/app/ws", headers=pub()),
    ):
        pass


def test_foreign_hosts_are_still_403(client: TestClient) -> None:
    assert client.get("/app/", headers={"host": "evil.com"}).status_code == 403


def test_without_a_public_host_the_public_name_is_403(rig: Rig, web: Path) -> None:
    app = create_app(rig.engine, media_dirs=(rig.images, rig.svgs), gate=None)
    with TestClient(app, base_url=BASE_URL) as c:
        assert c.get("/app/", headers={"host": PUBLIC}).status_code == 403
        assert c.get("/pair?c=x", headers={"host": PUBLIC}).status_code == 403
