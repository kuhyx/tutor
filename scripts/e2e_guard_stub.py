#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E stand-in for leetcode-guard's loopback ``GET /api/theory``.

``scripts/e2e_sandbox.sh up --guard-theory '<json>'`` starts it on a
sandbox-only port and points the sandbox server's ``TUTOR_GUARD_THEORY_URL``
at it, so the LeetCode bar (``DOCS-contract-leetcode-bar.md``) shows canned
numbers and never the live guard's. ``<json>`` is the route's ``theory`` map;
a missing ``day`` is filled with ``--day`` (the sandbox's today), so a canned
answer is not stale. Loopback only; it refuses the live guard's port.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any, Final

LIVE_PORT: Final = 8771  # leetcode-guard's own route: never answered from here
ROUTE: Final = "/api/theory"


def answer(body: str, day: str) -> bytes:
    """The route's JSON for the canned ``theory`` map ``body`` (``day``: if none)."""
    theory: Any = json.loads(body)
    if not isinstance(theory, dict):
        msg = "--body must be a JSON object"
        raise TypeError(msg)
    theory = theory.get("theory", theory)
    return json.dumps({"theory": {"day": day, **theory}}).encode()


def handler(reply: bytes) -> type[BaseHTTPRequestHandler]:
    """A request handler that answers ``GET /api/theory`` with ``reply``."""

    class Route(BaseHTTPRequestHandler):
        """200 for the route, 404 for anything else."""

        def get(self) -> None:
            found = self.path == ROUTE
            self.send_response(200 if found else 404)
            self.send_header("Content-Type", "application/json")
            body = reply if found else b"{}"
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: object) -> None:
            """Quiet: one line per poll is noise in the server log."""

    for verb in ("GET",):  # http.server dispatches on do_<VERB>
        setattr(Route, f"do_{verb}", Route.get)
    return Route


def main(argv: list[str] | None = None) -> int:
    """Serve on 127.0.0.1:``--port`` until stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--body", required=True, help="the route's theory map (JSON)")
    parser.add_argument("--day", required=True, help="YYYY-MM-DD, the sandbox's today")
    args = parser.parse_args(argv)
    if args.port == LIVE_PORT:
        parser.error(f"port {LIVE_PORT} is the live guard's")
    reply = answer(args.body, args.day)
    ThreadingHTTPServer(("127.0.0.1", args.port), handler(reply)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
