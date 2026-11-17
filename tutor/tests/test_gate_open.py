# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Opening the tutor page in the real browser, detached, never in-process."""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Any

from tutor import gate_open

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest


def test_the_url_is_the_local_tutor_app() -> None:
    assert gate_open.TUTOR_URL == "http://127.0.0.1:8778/app/"


def test_find_opener_prefers_the_first_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        shutil, "which", lambda n: f"/bin/{n}" if n == "firefox" else None
    )
    assert gate_open.find_opener() == "/bin/firefox"
    monkeypatch.setattr(shutil, "which", lambda _n: None)
    assert gate_open.find_opener() is None


def test_launch_spawns_detached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_open, "find_opener", lambda: "/bin/xdg-open")
    seen: list[tuple[Sequence[str], bool]] = []

    def spawn(args: Sequence[str], *, start_new_session: bool) -> Any:
        seen.append((args, start_new_session))

    result = gate_open.launch("http://x/", spawn=spawn)
    assert result.ok
    assert seen == [(("/bin/xdg-open", "http://x/"), True)]


def test_launch_without_an_opener_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_open, "find_opener", lambda: None)
    assert not gate_open.launch("http://x/").ok


def test_launch_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_open, "find_opener", lambda: "/bin/xdg-open")

    def boom(_args: Sequence[str], *, start_new_session: bool) -> Any:
        raise OSError(start_new_session)

    assert not gate_open.launch("http://x/", spawn=boom).ok


def test_default_spawner_is_popen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_open, "find_opener", lambda: "/bin/xdg-open")
    calls: list[Any] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    assert gate_open.launch("http://x/").ok
    assert calls[0][1] == {"start_new_session": True}
