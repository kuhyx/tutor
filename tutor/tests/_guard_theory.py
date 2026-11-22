# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A fake of leetcode-guard's loopback ``GET /api/theory`` (the LeetCode bar).

``conftest.guard_theory`` points ``TUTOR_GUARD_THEORY_URL`` at :data:`URL` and
swaps ``urllib.request.urlopen`` for :meth:`GuardFake.urlopen`, so no test can
reach the live ``127.0.0.1:8771``: that URL is an ``AssertionError``, not a
refused connection a ``except OSError`` would swallow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from email.message import Message
import io
import json
from typing import Any, Final, Self
import urllib.error
import urllib.request

REAL_URLOPEN: Final = urllib.request.urlopen  # before conftest swaps it
URL: Final = "http://guard-theory.invalid/api/theory"
LIVE: Final = "127.0.0.1:8771"
DAY: Final = "2027-01-15"  # the local day of tutor.tests._cur.T0 (Warsaw)


def theory(**over: Any) -> dict[str, Any]:
    """The route's answer (``DOCS-contract-leetcode-bar.md``), ``over`` applied."""
    body: dict[str, Any] = {
        "checked": True,
        "day": DAY,
        "unit": "a",
        "phase": "theory",
        "minutes_today": 5,
        "minutes_into_credit": 7,
        "minutes_per_credit": 12,
        "credits_today": 0,
        "needed": 7,
    }
    return {"theory": body | over}


class _Response(io.BytesIO):
    status = 200

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass
class GuardFake:
    """What the route answers next, and how it was asked."""

    # a dict / bytes body, an int (an HTTP error status) or an exception to raise
    reply: Any = field(default_factory=theory)
    status: int = 200
    timeouts: list[float | None] = field(default_factory=list)

    def urlopen(self, req: Any, timeout: float | None = None, **_: Any) -> _Response:
        """The patched ``urllib.request.urlopen``."""
        url = req if isinstance(req, str) else req.full_url
        if LIVE in url:
            msg = f"a test reached the live guard: {url}"
            raise AssertionError(msg)
        if url != URL:
            msg = "network disabled in tests"
            raise OSError(msg)
        self.timeouts.append(timeout)
        if isinstance(self.reply, Exception):
            raise self.reply
        if isinstance(self.reply, int):
            raise urllib.error.HTTPError(url, self.reply, "x", Message(), io.BytesIO())
        body = self.reply if isinstance(self.reply, bytes) else json.dumps(self.reply)
        found = _Response(body if isinstance(body, bytes) else body.encode())
        found.status = self.status
        return found


def install(patch: Any) -> GuardFake:
    """Point the env and ``urlopen`` at a fresh fake (``patch``: a MonkeyPatch)."""
    fake = GuardFake()
    patch.setenv("TUTOR_GUARD_THEORY_URL", URL)
    patch.setattr(urllib.request, "urlopen", fake.urlopen)
    return fake
