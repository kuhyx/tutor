# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The deploy installs the pins the live venv lacks (``tutor.live_deps``)."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys

import pytest

from tutor import live_deps

GIT = "relay @ git+https://github.com/kuhyx/utils@relay-v0.2.3#subdirectory=relay"


def _pin(version: str) -> tuple[str, str | None]:
    return version, None


def _git(rev: str) -> tuple[str, str | None]:
    return "0", rev


def _installed(found: dict[str, tuple[str, str | None]]) -> live_deps.Lookup:
    return found.get


def test_only_stale_or_missing_pins_are_listed() -> None:
    wanted = ["httpx==0.29.0", "fsrs==6.3.3", GIT, "gone==1.0", "loose>=1"]
    have = {
        "httpx": _pin("0.28.1"),
        "fsrs": _pin("6.3.3"),
        "relay": _git("relay-v0.2.2"),
    }
    assert live_deps.missing(wanted, _installed(have)) == [
        "httpx==0.29.0",
        GIT,
        "gone==1.0",
        "loose>=1",  # not an exact pin: cannot tell, so install it
    ]


def test_a_current_venv_needs_nothing() -> None:
    have = {"httpx": _pin("0.29.0"), "relay": _git("relay-v0.2.3")}
    assert live_deps.missing(["httpx==0.29.0", GIT], _installed(have)) == []
    # A git pin installed from an index (no direct_url.json) is reinstalled.
    assert live_deps.missing([GIT], _installed({"relay": _pin("0.2.3")})) == [GIT]


def test_main_prints_the_missing_pins(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    toml = tmp_path / "pyproject.toml"
    toml.write_text(
        '[project]\nname = "t"\ndependencies = ["pytest==0.0.1", "ruff==0.17.6"]\n'
    )
    assert live_deps.main([str(toml)]) == 0
    assert capsys.readouterr().out.splitlines() == ["pytest==0.0.1"]
    with pytest.raises(SystemExit):
        live_deps.main([])


def test_installed_reads_this_venv() -> None:
    version, rev = live_deps.installed("httpx") or ("", "")
    assert (version, rev) == (__import__("httpx").__version__, None)
    relay = live_deps.installed("rtdb-relay")
    assert relay is not None
    assert str(relay[1]).startswith("rtdb-relay-v")
    assert live_deps.installed("no-such-dist-here") is None


def test_runs_as_a_module(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    toml = tmp_path / "pyproject.toml"
    toml.write_text('[project]\nname = "t"\n')
    monkeypatch.setattr(sys, "argv", ["live_deps", str(toml)])
    monkeypatch.delitem(sys.modules, "tutor.live_deps")
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("tutor.live_deps", run_name="__main__")
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == ""


def test_the_deploy_syncs_the_live_venv_before_the_release() -> None:
    """``tutor_deploy.sh`` installs missing pins with the unit's own python."""
    script = (Path(__file__).parents[2] / "scripts" / "tutor_deploy.sh").read_text(
        encoding="utf-8"
    )
    body = script.split("\nmain() {", 1)[1]
    assert body.index("sync_live_deps") < body.index("copy_release")
    sync = script.split("sync_live_deps() {", 1)[1].split("\n}\n", 1)[0]
    assert "-m tutor.live_deps" in sync
    assert "-m pip install" in sync
