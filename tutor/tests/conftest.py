# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Every tutor test runs in a private HOME and data dir, with no network.

HOME moves too, so a fallback to ``~/.local/share/tutor`` (the real
ledger), ``~/.cache`` or ``~/.claude`` can only ever land in ``tmp_path``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
import urllib.request

import httpx
import pytest

from tutor import images

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from pathlib import Path

    from code_runner import CaseResult, Example

KEY = b"tutor-test-key-not-the-real-one"


def _offline(*_: object, **__: object) -> object:
    msg = "network disabled in tests"
    raise OSError(msg)


async def _offline_async(*_: object, **__: object) -> object:
    msg = "network disabled in tests (httpx: use tests/_fake_rtdb.py)"
    raise httpx.ConnectError(msg)


def _memoised(
    real: Callable[..., list[CaseResult]],
) -> Callable[..., list[CaseResult]]:
    """``code_runner.run`` that sandboxes each distinct snippet once per session.

    The mock-test suites re-run the same seed snippets dozens of times (a bwrap
    start each); a run is a pure function of its inputs, so repeats are served
    from memory. Every distinct input still goes through the real sandbox, and
    ``code_runner``'s own tests (a different tree) never see this wrapper.
    """
    seen: dict[tuple[str, str, str, str], list[CaseResult]] = {}

    def run(
        lang: str,
        code: str,
        starter: str,
        examples: Sequence[Example],
        **kwargs: Any,
    ) -> list[CaseResult]:
        if kwargs:
            return real(lang, code, starter, examples, **kwargs)
        key = (lang, code, starter, repr(list(examples)))
        if key not in seen:
            seen[key] = real(lang, code, starter, examples)
        return list(seen[key])

    return run


@pytest.fixture(scope="session", autouse=True)
def memoised_sandbox() -> Iterator[None]:
    """Serve repeated identical sandbox runs from memory (see ``_memoised``)."""
    import code_runner  # after collection: its package conftest must import first

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(code_runner, "run", _memoised(code_runner.run))
        yield


@pytest.fixture(autouse=True)
def tutor_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect HOME, the data dir, the key and the image cache; block the network."""
    home = tmp_path / "home"
    home.mkdir()
    key = tmp_path / "hmac.key"
    key.write_bytes(KEY + b"\n")
    monkeypatch.setenv("HOME", str(home))
    # "Local day" is the machine's zone; tests state Warsaw clock times, and a
    # UTC runner (CI) would put 00:01 Warsaw on the previous day.
    monkeypatch.setenv("TZ", "Europe/Warsaw")
    time.tzset()
    monkeypatch.setenv("TUTOR_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("TUTOR_KEY", str(key))
    monkeypatch.setenv("TUTOR_IMAGE_CACHE", str(tmp_path / "images"))
    monkeypatch.setenv("FOCUS_PROJECT_DATA", str(tmp_path / "focus"))  # optional dep
    monkeypatch.delenv("TUTOR_RELAY", raising=False)
    monkeypatch.delenv("TUTOR_ANKI_COLLECTION", raising=False)  # default: under HOME
    monkeypatch.setattr(urllib.request, "urlopen", _offline)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", _offline_async
    )
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _offline)
    yield tmp_path
    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def commons(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """term -> CommonsImage, None, or an exception to raise."""
    found: dict[str, Any] = {}

    def fetch(term: str) -> Any:
        hit = found[term]
        if isinstance(hit, Exception):
            raise hit
        return hit

    monkeypatch.setattr(images, "fetch", fetch)
    monkeypatch.setattr(
        images, "content_block", lambda img: {"type": "image", "file": img.file}
    )
    return found
