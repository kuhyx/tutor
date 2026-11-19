# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Keep every other web page out of the tutor's HTTP server.

The server listens on loopback, but any page open in the browser can still
reach it: a cross-site ``text/plain`` POST is a "simple" request (no
preflight) and DNS rebinding makes a hostile name resolve to 127.0.0.1. A
reached ``/api/start`` or ``/api/message`` runs Claude with its full tool
preset, so this guard sits in front of every route:

* ``Host`` must be exactly a loopback origin of the bound port, else 403
  (that is what stops DNS rebinding);
* a state-changing method must carry ``Content-Type: application/json``,
  else 415 (a page cannot send that cross-site without a preflight, which
  the server never answers);
* such a request that carries ``Origin`` must carry the page's own origin
  (the one its ``Host`` names), else 403.

curl, the scripted learner and the deploy smoke test send a loopback Host and
no Origin, so they pass unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

_SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})
_LOOPBACK_NAMES: Final = ("127.0.0.1", "localhost", "[::1]")


def local_hosts(port: int) -> frozenset[str]:
    """The ``Host`` values the page itself sends for ``port``."""
    return frozenset(f"{name}:{port}" for name in _LOOPBACK_NAMES)


def _is_json(content_type: str) -> bool:
    return content_type.split(";", 1)[0].strip().lower() == "application/json"


class LocalGuard:
    """ASGI middleware: refuse requests that did not come from the tutor's page."""

    def __init__(self, app: ASGIApp, *, port: int) -> None:
        """Wrap ``app``; only loopback origins of ``port`` get through."""
        self.app = app
        self.hosts = local_hosts(port)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Answer 403 / 415 for a foreign request, else pass it on."""
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        refusal = self._refusal(scope)
        if refusal is None:
            await self.app(scope, receive, send)
        elif scope["type"] == "http":
            await PlainTextResponse(refusal[1], status_code=refusal[0])(
                scope, receive, send
            )
        else:  # websocket: close before accepting
            await send({"type": "websocket.close", "code": 1008})

    def _refusal(self, scope: Scope) -> tuple[int, str] | None:
        headers = Headers(scope=scope)
        host = headers.get("host", "").lower()
        if host not in self.hosts:
            return 403, "forbidden host"
        if scope["type"] != "http" or scope["method"] in _SAFE_METHODS:
            return None
        if not _is_json(headers.get("content-type", "")):
            return 415, "application/json required"
        origin = headers.get("origin")
        if origin is not None and origin.lower() != f"http://{host}":
            return 403, "forbidden origin"
        return None
