# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The sandboxed CLI's login copy: access token only, refreshed on the host."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import stat
import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from tutor import model_login

if TYPE_CHECKING:
    import pytest

OAUTH: dict[str, Any] = {
    "accessToken": "access-1",
    "refreshToken": "refresh-secret",
    "expiresAt": 10_000_000,
    "scopes": ["user:inference"],
    "subscriptionType": "max",
}
HOST_LOGIN: dict[str, Any] = {
    "claudeAiOauth": OAUTH,
    "mcpOAuth": {"gmail": {"accessToken": "gmail-secret"}},
}


def host_login(home: Path, login: dict[str, Any] = HOST_LOGIN) -> Path:
    """Write kuhy's (fake) CLI login under ``home``."""
    path = home / ".claude" / ".credentials.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(login), encoding="utf-8")
    return path


def copied(box: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (box / ".claude/.credentials.json").read_text(encoding="utf-8")
    )
    return data


def test_the_copy_keeps_only_the_access_token(tutor_sandbox: Path) -> None:
    host_login(tutor_sandbox / "home")
    box = tutor_sandbox / "box"
    assert model_login.sync_login(box) == 10_000_000
    assert copied(box) == {
        "claudeAiOauth": {
            "accessToken": "access-1",
            "expiresAt": 10_000_000,
            "scopes": ["user:inference"],
            "subscriptionType": "max",
        }
    }
    text = (box / ".claude/.credentials.json").read_text(encoding="utf-8")
    assert "refresh-secret" not in text
    assert "gmail-secret" not in text
    mode = (box / ".claude/.credentials.json").stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_no_host_login_writes_nothing(tutor_sandbox: Path) -> None:
    assert model_login.sync_login(tutor_sandbox / "box") is None
    assert not (tutor_sandbox / "box/.claude/.credentials.json").exists()


def test_a_login_without_expiry_is_copied(tutor_sandbox: Path) -> None:
    host_login(tutor_sandbox / "home", {"claudeAiOauth": {"accessToken": "a"}})
    assert model_login.sync_login(tutor_sandbox / "box") is None
    assert copied(tutor_sandbox / "box")["claudeAiOauth"] == {"accessToken": "a"}


def test_an_expiring_login_is_refreshed_on_the_host_first(
    tutor_sandbox: Path,
) -> None:
    home = tutor_sandbox / "home"
    host_login(home, {"claudeAiOauth": {**OAUTH, "expiresAt": 1_100_000}})
    calls: list[str] = []

    def refresh() -> None:
        calls.append("refresh")
        fresh = {"claudeAiOauth": {"accessToken": "access-2", "expiresAt": 9e12}}
        host_login(home, fresh)

    box = tutor_sandbox / "box"
    model_login.Login(box, refresh=refresh, now=lambda: 1000.0).ensure()
    assert calls == ["refresh"]  # 100 s left: inside the CLI's 5 min margin
    assert copied(box)["claudeAiOauth"]["accessToken"] == "access-2"


def test_a_fresh_login_is_only_copied(tutor_sandbox: Path) -> None:
    host_login(tutor_sandbox / "home")  # expires at 10 000 s
    calls: list[str] = []
    box = tutor_sandbox / "box"
    model_login.Login(
        box, refresh=lambda: calls.append("x"), now=lambda: 1000.0
    ).ensure()
    assert calls == []
    assert copied(box)["claudeAiOauth"]["accessToken"] == "access-1"


def test_a_failing_refresh_is_logged_not_raised(
    tutor_sandbox: Path, caplog: pytest.LogCaptureFixture
) -> None:
    host_login(tutor_sandbox / "home", {"claudeAiOauth": {**OAUTH, "expiresAt": 0}})

    def refresh() -> None:
        raise subprocess.CalledProcessError(1, "claude")

    box = tutor_sandbox / "box"
    model_login.Login(box, refresh=refresh, now=lambda: 1000.0).ensure()
    assert "could not refresh" in caplog.text


def test_the_default_refresh_runs_beside_the_box(
    tutor_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host_login(tutor_sandbox / "home", {"claudeAiOauth": {**OAUTH, "expiresAt": 0}})
    seen: list[Path] = []
    monkeypatch.setattr(model_login, "refresh_host_login", seen.append)
    model_login.Login(tutor_sandbox / "root/home").ensure()
    assert seen == [tutor_sandbox / "root"]


def test_refresh_runs_the_host_cli_with_nothing_loaded(
    tutor_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def run(cmd: list[str], **kwargs: Any) -> None:
        seen.update(cmd=cmd, **kwargs)

    monkeypatch.setenv("TUTOR_MODEL_CLI", "/opt/claude")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setattr(subprocess, "run", run)
    model_login.refresh_host_login(tutor_sandbox / "root")
    assert seen["cmd"][0] == "/opt/claude"
    for flag in ("--tools=", "--setting-sources=", "--strict-mcp-config"):
        assert flag in seen["cmd"]
    assert seen["cwd"] == tutor_sandbox / "root"
    assert seen["cwd"].is_dir()
    assert "CLAUDECODE" not in seen["env"]
    assert seen["check"] is True
    assert seen["timeout"] <= 60


def test_real_cli_order(tutor_sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sdk = tutor_sandbox / "sdk"
    (sdk / "_bundled").mkdir(parents=True)
    fake_sdk = SimpleNamespace(__file__=str(sdk / "x.py"))
    monkeypatch.setattr(model_login, "claude_agent_sdk", fake_sdk)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    assert model_login.real_cli() == sdk / "_bundled" / "claude"  # nothing found
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
    assert model_login.real_cli() == Path("/usr/bin/claude")
    (sdk / "_bundled" / "claude").write_text("", encoding="utf-8")
    assert model_login.real_cli() == sdk / "_bundled" / "claude"
    monkeypatch.setenv("TUTOR_MODEL_CLI", "/opt/claude")
    assert model_login.real_cli() == Path("/opt/claude")


def test_host_login_file_honours_claude_config_dir(
    tutor_sandbox: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home_file = tutor_sandbox / "home/.claude/.credentials.json"
    assert model_login.host_login_file() == home_file
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tutor_sandbox / "cfg"))
    assert model_login.host_login_file() == tutor_sandbox / "cfg/.credentials.json"
