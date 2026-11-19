# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Helpers for the public-hostname tests: pair a phone, build public headers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor.tests._fakes import BASE_URL

if TYPE_CHECKING:
    from starlette.testclient import TestClient

PUBLIC = "tutor.test"
JSON = {"content-type": "application/json", "origin": BASE_URL}
CREDS = {
    "id_token": "a.b.c",
    "refresh_token": "r",
    "expires_at": "2099-01-01T00:00:00Z",
}


def mint(client: TestClient) -> str:
    reply = client.post("/api/pair", json={}, headers=JSON)
    assert reply.status_code == 200
    assert reply.headers["cache-control"] == "no-store"
    url = str(reply.json()["url"])
    assert url.startswith(f"https://{PUBLIC}/pair?c=")
    return url.split("?c=", 1)[1]


def pair(client: TestClient) -> str:
    """Pair a phone through the public host; return its cookie header value."""
    redeemed = client.get(f"/pair?c={mint(client)}", headers={"host": PUBLIC})
    assert redeemed.status_code == 303
    assert redeemed.headers["location"] == "/"
    cookie = redeemed.headers["set-cookie"]
    return cookie.split(";", 1)[0]


def pub(cookie: str | None = None, **extra: str) -> dict[str, str]:
    headers = {"host": PUBLIC, **extra}
    if cookie:
        headers["cookie"] = cookie
    return headers
