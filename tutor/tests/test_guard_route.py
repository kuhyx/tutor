# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``guard_route.fetch``: one bounded, cached, total GET of the guard's route."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
import time
from typing import TYPE_CHECKING
import urllib.request

import pytest

from tutor import guard_route
from tutor.tests._guard_theory import REAL_URLOPEN, GuardFake, theory

if TYPE_CHECKING:
    from collections.abc import Iterator


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr(guard_route, "clock", fake)
    return fake


class _Drip(BaseHTTPRequestHandler):
    """200 with a Content-Length it fills at one byte per 0.3 s."""

    def do_GET(self) -> None:
        body = json.dumps(theory()).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            for byte in body:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                time.sleep(0.3)
        except OSError:
            logging.getLogger(__name__).warning("the reader gave up")

    def log_message(self, fmt: str, *args: object) -> None:
        """Quiet."""


@pytest.fixture
def drip(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Drip)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(urllib.request, "urlopen", REAL_URLOPEN)
    monkeypatch.setenv(
        "TUTOR_GUARD_THEORY_URL", f"http://127.0.0.1:{server.server_port}/api/theory"
    )
    yield
    server.shutdown()
    server.server_close()


@pytest.mark.usefixtures("drip")
def test_a_dripping_guard_costs_under_a_second_and_reads_as_unchecked() -> None:
    started = time.monotonic()
    assert guard_route.fetch() is None
    assert time.monotonic() - started < 1.0
    started = time.monotonic()
    assert guard_route.fetch() is None  # inside the retry window: no wait at all
    assert time.monotonic() - started < 0.1


@pytest.mark.usefixtures("drip")
def test_a_body_past_its_deadline_is_given_up_in_the_worker() -> None:
    """The worker's own deadline, checked here, not after the test has returned."""
    with pytest.raises(TimeoutError, match="too slow"):
        guard_route._get(time.monotonic())


def test_a_success_is_served_for_5_s_from_one_call(
    guard_theory: GuardFake, clock: _Clock
) -> None:
    first = guard_route.fetch()
    assert first == theory()["theory"]
    clock.now += guard_route.CACHE_S - 1
    guard_theory.reply = OSError("down now")
    assert guard_route.fetch() == first  # a burst of publishes: one network call
    assert len(guard_theory.timeouts) == 1
    clock.now += 1
    assert guard_route.fetch() is None  # the cache is over: ask, and it is down
    assert len(guard_theory.timeouts) == 2


@pytest.mark.parametrize(
    "reply",
    [
        b"[" * 4000 + b"]" * 96,  # nested past the parser's depth
        b"<html>" + b"x" * 5000,  # 200 with HTML, over the body cap
        b"<html>not the route</html>",  # 200 with HTML
        json.dumps(theory(unit="u" * 5000)).encode(),  # a good map, over the cap
    ],
    ids=["nested", "big-html", "html", "over-cap"],
)
def test_a_hostile_answer_is_unchecked_and_never_raises(
    guard_theory: GuardFake, reply: bytes
) -> None:
    guard_theory.reply = reply
    assert guard_route.fetch() is None


def test_an_answer_at_the_cap_still_parses(guard_theory: GuardFake) -> None:
    body = json.dumps(theory(unit="u" * 3000)).encode()
    assert len(body) <= guard_route.MAX_BODY
    guard_theory.reply = body
    assert guard_route.fetch() is not None
