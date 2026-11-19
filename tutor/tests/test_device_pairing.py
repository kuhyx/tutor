# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Pairing a phone: one-time codes, the device cookie, the device file."""

from __future__ import annotations

import hashlib
import json
import stat
from typing import TYPE_CHECKING

import pytest

from tutor.device_gate import COOKIE
from tutor.tests._public_support import JSON, PUBLIC, mint, pair, pub

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.testclient import TestClient

    from tutor.device_gate import PublicGate
    from tutor.tests._public_fixtures import Clock


def test_pairing_round_trip_then_the_page_loads(client: TestClient) -> None:
    cookie = pair(client)
    page = client.get("/app/", headers=pub(cookie))
    assert page.status_code == 200
    assert "tutor page" in page.text
    assert client.head("/app/", headers=pub(cookie)).status_code == 200
    assert client.get("/", headers=pub(cookie)).status_code == 307


def test_the_cookie_is_long_lived_secure_and_httponly(
    client: TestClient, gate: PublicGate
) -> None:
    redeemed = client.get(f"/pair?c={mint(client)}", headers={"host": PUBLIC})
    line = redeemed.headers["set-cookie"]
    assert line.startswith(f"{COOKIE}=")
    for part in ("Max-Age=34560000", "Path=/", "Secure", "HttpOnly", "SameSite=lax"):
        assert part.lower() in line.lower()
    assert redeemed.headers["cache-control"] == "no-store"


def test_the_store_keeps_only_a_hash_in_a_private_file(
    client: TestClient, tmp_path: Path
) -> None:
    cookie = pair(client)
    token = cookie.split("=", 1)[1]
    path = tmp_path / "devices.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert [r["sha256"] for r in rows] == [hashlib.sha256(token.encode()).hexdigest()]
    assert token not in path.read_text(encoding="utf-8")


def test_a_pairing_code_works_once(client: TestClient) -> None:
    code = mint(client)
    assert client.get(f"/pair?c={code}", headers=pub()).status_code == 303
    assert client.get(f"/pair?c={code}", headers=pub()).status_code == 403


def test_a_pairing_code_expires_after_five_minutes(
    client: TestClient, clock: Clock
) -> None:
    code = mint(client)
    clock.now += 301
    assert client.get(f"/pair?c={code}", headers=pub()).status_code == 403


@pytest.mark.parametrize("query", ["", "?c=", "?c=nope", "?c=a&c=b", "?x=1"])
def test_bad_pairing_codes_are_403_with_no_cookie(
    client: TestClient, query: str
) -> None:
    reply = client.get(f"/pair{query}", headers=pub())
    assert reply.status_code == 403
    assert "set-cookie" not in reply.headers


def test_at_most_five_codes_are_pending(client: TestClient) -> None:
    codes = [mint(client) for _ in range(6)]
    assert client.get(f"/pair?c={codes[0]}", headers=pub()).status_code == 403
    assert client.get(f"/pair?c={codes[5]}", headers=pub()).status_code == 303


def test_minting_is_the_pcs_alone(client: TestClient) -> None:
    cookie = pair(client)
    for headers in (pub(), pub(cookie)):
        reply = client.post(
            "/api/pair", json={}, headers={**headers, **JSON, "host": PUBLIC}
        )
        assert reply.status_code in {401, 403}
    # The PC itself still needs the usual JSON content type.
    plain = client.post(
        "/api/pair", content=b"{}", headers={"content-type": "text/plain"}
    )
    assert plain.status_code == 415
