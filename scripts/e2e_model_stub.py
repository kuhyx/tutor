#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E model stub: an Anthropic API that refuses every call (HTTP 400).

``scripts/e2e_sandbox.sh up --model-down refuse`` points the sandbox
worker's Claude CLI at it (``ANTHROPIC_BASE_URL``), so a model call fails
the way a bad request does: an API error with a 4xx status, which
``tutor.outage`` does not call an outage. The worker reports
``model_error`` (``error_kind: model_failed``), not ``claude_unavailable``.
Loopback only; never the real API.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

_BODY = json.dumps(
    {
        "type": "error",
        "error": {"type": "invalid_request_error", "message": "e2e stub: refused"},
    }
).encode()


class _Refuse(BaseHTTPRequestHandler):
    """400 for anything."""

    def refuse(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(_BODY)))
        self.end_headers()
        self.wfile.write(_BODY)

    def log_message(self, fmt: str, *args: object) -> None:
        """Quiet: one line per call is noise in the server log."""


# BaseHTTPRequestHandler dispatches on do_<VERB>: every verb refuses.
for _verb in ("GET", "POST", "HEAD"):
    setattr(_Refuse, f"do_{_verb}", _Refuse.refuse)


def main() -> int:
    """Serve on 127.0.0.1:``--port`` until stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    port = parser.parse_args().port
    ThreadingHTTPServer(("127.0.0.1", port), _Refuse).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
