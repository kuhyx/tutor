# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One bounded GET of leetcode-guard's loopback ``/api/theory`` (display only).

Whatever the guard does, :func:`fetch` returns within :data:`TOTAL_S` and never
raises: an unreachable, slow, dripping, oversized, hostile or malformed answer
is ``None`` ("could not check"). The caller holds the publisher's lock, so:

- the GET runs on a one-worker pool and the caller waits ``TOTAL_S`` in all
  (``urlopen``'s timeout is per socket operation; a server dripping a byte
  every 0.3 s would otherwise hold it for as long as it likes);
- a failure turns the route off for :data:`RETRY_S` (no second 0.5 s wait on
  the next publish); a success is served for :data:`CACHE_S` (a burst of
  publishes makes one call);
- the body is read in chunks and refused above :data:`MAX_BODY` bytes.

The state is logged on a CHANGE only (reachable -> unreachable and back). The
URL resolves at call time (``TUTOR_GUARD_THEORY_URL``; tests fake it).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import logging
import os
import threading
import time
from typing import TYPE_CHECKING, Any, Final
import urllib.error
import urllib.parse
import urllib.request

if TYPE_CHECKING:
    from collections.abc import Callable

URL_ENV: Final = "TUTOR_GUARD_THEORY_URL"
GUARD_THEORY_URL: Final = "http://127.0.0.1:8771/api/theory"
TOTAL_S: Final = 0.5  # the whole fetch, not one socket operation
RETRY_S: Final = 30.0  # after a failure: "could not check" without asking
CACHE_S: Final = 5.0  # after a success: the same answer without asking
MAX_BODY: Final = 4096
_OK: Final = 200
_logger = logging.getLogger(__name__)
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="guard-theory")
clock: Callable[[], float] = time.monotonic  # tests move it


class _State:
    """What the last calls learned (``clock()`` readings, not wall time)."""

    def __init__(self) -> None:
        """Nothing learned yet."""
        self.reachable: bool | None = None  # ``None`` until the first call
        self.retry_at = float("-inf")
        self.cached: dict[str, Any] | None = None
        self.cache_until = float("-inf")

    def reset(self) -> None:
        """Forget everything."""
        self.reachable = None
        self.retry_at = self.cache_until = float("-inf")
        self.cached = None


_state = _State()


def forget_state() -> None:
    """Treat the next call as the first, with nothing cached (tests)."""
    _state.reset()


def theory_url() -> str:
    """The route's URL, read at call time (``TUTOR_GUARD_THEORY_URL`` moves it)."""
    return os.environ.get(URL_ENV) or GUARD_THEORY_URL


def _news(*, reachable: bool) -> bool:
    """Record the route's state; whether it changed in a way worth a line.

    Down after up (or the first time), and up after down. The very first
    success is silent.
    """
    before, _state.reachable = _state.reachable, reachable
    return before is not reachable and (not reachable or before is False)


def _get(stop: float) -> object:
    """The route's JSON body; raises ``OSError``, ``ValueError`` or the parser's."""
    url = theory_url()
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "http":
        msg = f"not an http URL: {url!r}"
        raise ValueError(msg)
    # Rebuilt on a literal ``http://``: no ``file:`` or custom scheme reaches urlopen.
    query = f"?{parts.query}" if parts.query else ""
    with urllib.request.urlopen(
        urllib.request.Request(f"http://{parts.netloc}{parts.path}{query}"),
        timeout=TOTAL_S,
    ) as response:
        if response.status != _OK:
            msg = f"HTTP {response.status}"
            raise OSError(msg)
        body = bytearray()
        while chunk := response.read1(MAX_BODY + 1 - len(body)):
            body += chunk
            if len(body) > MAX_BODY:
                msg = f"answer over {MAX_BODY} bytes"
                raise ValueError(msg)
            if time.monotonic() > stop:
                msg = "guard theory route too slow"
                raise TimeoutError(msg)
        return json.loads(body)


def _failed(exc: BaseException) -> None:
    """Turn the route off for :data:`RETRY_S`."""
    if isinstance(exc, urllib.error.HTTPError):
        exc.close()  # it holds the connection's body
    _state.retry_at = clock() + RETRY_S


def _ask() -> dict[str, Any] | None:
    future = _pool.submit(_get, time.monotonic() + TOTAL_S)
    try:
        # A timeout is an OSError; BadStatusLine / IncompleteRead are
        # HTTPExceptions; a nested body is a RecursionError.
        body = future.result(timeout=TOTAL_S)
    except (OSError, ValueError, RecursionError, http.client.HTTPException) as exc:
        _failed(exc)
        if _news(reachable=False):  # one line per state change
            _logger.warning(
                "guard theory route unreachable, bar blank: %s: %s",
                type(exc).__name__,
                exc,
            )
        return None
    theory = body.get("theory") if isinstance(body, dict) else None
    if not isinstance(theory, dict):
        if _news(reachable=False):
            _logger.warning("guard theory route gave no theory map, bar blank")
        return None
    if _news(reachable=True):
        _logger.warning("guard theory route reachable again")
    _state.cached, _state.cache_until = theory, clock() + CACHE_S
    return theory


def fetch() -> dict[str, Any] | None:
    """The route's ``theory`` map, or ``None`` when it did not give one."""
    with _lock:
        now = clock()
        if now < _state.retry_at:
            return None  # failed a moment ago: do not wait for it again
        if _state.cached is not None and now < _state.cache_until:
            return _state.cached
        _state.cached = None
        return _ask()
