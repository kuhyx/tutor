# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The Flutter web client mount and its one-shot credentials route."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.testclient import TestClient

from tutor import webapp
from tutor.engine import Engine
from tutor.server import create_app
from tutor.tests._fakes import BASE_URL

if TYPE_CHECKING:
    import pytest

CREDS = {
    "id_token": "a.b.c",
    "refresh_token": "r",
    "expires_at": "2099-01-01T00:00:00Z",
}


def _client(web: Path, creds: Path) -> TestClient:
    return TestClient(
        Starlette(routes=webapp.webapp_routes(web, creds)),
        base_url="http://127.0.0.1:8778",
    )


def _build(web: Path) -> None:
    web.mkdir()
    (web / "index.html").write_text("<html>tutor</html>", encoding="utf-8")
    (web / "main.dart.wasm").write_bytes(b"\0asm")


def test_serves_the_build_with_revalidation(tmp_path: Path) -> None:
    web = tmp_path / "web"
    _build(web)
    client = _client(web, tmp_path / "none.json")
    page = client.get("/app/")
    assert page.status_code == 200
    assert "tutor" in page.text
    assert page.headers["cache-control"] == "no-cache"
    wasm = client.get("/app/main.dart.wasm")
    assert wasm.headers["content-type"] == "application/wasm"
    moved = client.get("/app", follow_redirects=False)
    assert moved.status_code == 308
    assert moved.headers["location"] == "/app/"


def test_unbuilt_says_how_to_build(tmp_path: Path) -> None:
    page = _client(tmp_path / "missing", tmp_path / "none.json").get("/app/")
    assert page.status_code == 503
    assert "flutter build web" in page.text


def test_credentials_served_once(tmp_path: Path) -> None:
    creds = tmp_path / "auth.json"
    creds.write_text(json.dumps({**CREDS, "extra": 1}), encoding="utf-8")
    client = _client(tmp_path / "web", creds)
    first = client.get("/app/sync-credentials")
    assert first.status_code == 200
    assert first.json() == CREDS
    assert first.headers["cache-control"] == "no-store"
    assert client.get("/app/sync-credentials").status_code == 404


def test_credentials_refused(tmp_path: Path) -> None:
    creds = tmp_path / "auth.json"
    missing = _client(tmp_path / "web", creds)
    assert missing.get("/app/sync-credentials").status_code == 404
    creds.write_text("not json", encoding="utf-8")
    assert missing.get("/app/sync-credentials").status_code == 404
    creds.write_text(json.dumps(["x"]), encoding="utf-8")
    assert missing.get("/app/sync-credentials").status_code == 404
    creds.write_text(json.dumps({**CREDS, "expires_at": 1}), encoding="utf-8")
    assert missing.get("/app/sync-credentials").status_code == 404
    creds.write_text(json.dumps(CREDS), encoding="utf-8")
    cross = missing.get(
        "/app/sync-credentials", headers={"sec-fetch-site": "cross-site"}
    )
    assert cross.status_code == 404
    rebound = TestClient(
        Starlette(routes=webapp.webapp_routes(tmp_path, creds)),
        base_url="http://evil.example",
    )
    assert rebound.get("/app/sync-credentials").status_code == 404
    # Refusals did not burn the one serve.
    typed = missing.get("/app/sync-credentials", headers={"sec-fetch-site": "none"})
    assert typed.status_code == 200


def _pass_client(
    tmp_path: Path, secret: Path, host: str = "127.0.0.1:8778"
) -> TestClient:
    routes = webapp.webapp_routes(tmp_path / "web", tmp_path / "none.json", secret)
    return TestClient(Starlette(routes=routes), base_url=f"http://{host}")


def test_passphrase_served_once(tmp_path: Path) -> None:
    secret = tmp_path / "password"
    secret.write_text("hunter2\n", encoding="utf-8")
    client = _pass_client(tmp_path, secret)
    first = client.get("/app/sync-passphrase")
    assert first.status_code == 200
    assert first.json() == {"passphrase": "hunter2"}
    assert first.headers["cache-control"] == "no-store"
    assert client.get("/app/sync-passphrase").status_code == 404


def test_passphrase_refused(tmp_path: Path) -> None:
    secret = tmp_path / "password"
    client = _pass_client(tmp_path, secret)
    assert client.get("/app/sync-passphrase").status_code == 404
    secret.write_text("  \n", encoding="utf-8")
    assert client.get("/app/sync-passphrase").status_code == 404
    secret.write_text("hunter2", encoding="utf-8")
    cross = client.get("/app/sync-passphrase", headers={"sec-fetch-site": "cross-site"})
    assert cross.status_code == 404
    rebound = _pass_client(tmp_path, secret, host="evil.example")
    assert rebound.get("/app/sync-passphrase").status_code == 404
    # Refusals did not burn the one serve.
    assert client.get("/app/sync-passphrase").json() == {"passphrase": "hunter2"}


def test_passphrase_defaults_to_crdt_sync_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(webapp.CRDT_SYNC_FILE_ENV, raising=False)
    secret = Path.home() / ".config" / "crdt-sync" / "password"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text("pc-secret", encoding="utf-8")
    client = TestClient(
        Starlette(routes=webapp.webapp_routes(tmp_path, tmp_path / "none.json")),
        base_url="http://127.0.0.1:8778",
    )
    assert client.get("/app/sync-passphrase").json() == {"passphrase": "pc-secret"}
    monkeypatch.setenv(webapp.CRDT_SYNC_FILE_ENV, str(tmp_path / "sandbox"))
    assert webapp.passphrase_from_env() == tmp_path / "sandbox"


def test_paths_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(webapp.WEB_DIR_ENV, raising=False)
    monkeypatch.delenv(webapp.CREDENTIALS_ENV, raising=False)
    assert webapp.web_dir_from_env() == webapp.DEFAULT_WEB_DIR
    assert webapp.credentials_from_env().parts[-3:] == (
        ".config",
        "tutor",
        "firebase_auth.json",
    )
    monkeypatch.setenv(webapp.WEB_DIR_ENV, str(tmp_path / "w"))
    monkeypatch.setenv(webapp.CREDENTIALS_ENV, str(tmp_path / "c.json"))
    assert webapp.paths_from_env() == (tmp_path / "w", tmp_path / "c.json")
    assert webapp.web_dir_from_env() == tmp_path / "w"
    assert webapp.credentials_from_env() == tmp_path / "c.json"


def test_server_mounts_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    web = tmp_path / "web"
    _build(web)
    monkeypatch.setenv(webapp.WEB_DIR_ENV, str(web))
    with TestClient(create_app(Engine()), base_url=BASE_URL) as client:
        assert client.get("/app/").status_code == 200
        assert client.get("/").status_code == 200


def test_standalone_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    web = tmp_path / "web"
    _build(web)
    monkeypatch.setenv(webapp.WEB_DIR_ENV, str(web))
    client = TestClient(webapp.standalone_app())
    assert client.get("/app/").status_code == 200
    assert client.get("/").status_code == 404
