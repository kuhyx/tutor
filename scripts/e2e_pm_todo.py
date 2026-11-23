#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Flow F32's FAKE todo MCP server: records every ``add_task``, files nothing.

``tutor.postmortem.todo`` speaks MCP over HTTP to ``TUTOR_TODO_URL``; the F32
driver (``scripts/e2e_postmortem.py``) points that at this server, so the
real ``http_post`` path runs and kuhy's todo app (``127.0.0.1:8735``) is never
reached. It answers ``initialize`` with an ``Mcp-Session-Id`` header,
``notifications/initialized`` with 202 and ``tools/call add_task`` with an
event-stream reply, as the real server does; each task's arguments become one
line of ``--out`` (JSONL). A wrong bearer token or session id gets 401/400.
Loopback only; run as a ``systemd-run --user`` unit by the driver.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from typing import Any, ClassVar, Final

SESSION: Final = "e2e-f32-session"


class Handler(BaseHTTPRequestHandler):
    """One MCP POST; the class attributes are set by :func:`main`."""

    out: ClassVar[Path]
    token: ClassVar[str]

    def _reply(self, status: int, body: str, headers: dict[str, str]) -> None:
        data = body.encode()
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        """Answer one JSON-RPC message."""
        if self.headers.get("Authorization") != f"Bearer {self.token}":
            self._reply(401, "bad token", {})
            return
        size = int(self.headers.get("Content-Length") or 0)
        message: dict[str, Any] = json.loads(self.rfile.read(size) or b"{}")
        method = message.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}}
            body = {"jsonrpc": "2.0", "id": message.get("id"), "result": result}
            plain = {"Content-Type": "application/json", "Mcp-Session-Id": SESSION}
            self._reply(200, json.dumps(body), plain)
            return
        if self.headers.get("Mcp-Session-Id") != SESSION:
            self._reply(400, "no session", {})
            return
        if method == "notifications/initialized":
            self._reply(202, "", {})
            return
        params = message.get("params") or {}
        if method != "tools/call" or params.get("name") != "add_task":
            self._reply(400, f"unexpected {method}", {})
            return
        with self.out.open("a", encoding="utf-8") as sink:
            row = {"at": time.time(), "args": params.get("arguments")}
            sink.write(json.dumps(row) + "\n")
        text = {"type": "text", "text": f"e2e task filed at {time.time():.0f}"}
        body = {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {"content": [text]},
        }
        stream = f"event: message\ndata: {json.dumps(body)}\n\n"
        self._reply(200, stream, {"Content-Type": "text/event-stream"})

    def log_message(self, *args: object) -> None:
        """Quiet: the JSONL file is the record."""


def main() -> int:
    """Serve until the unit is stopped."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    args = parser.parse_args()
    Handler.out = args.out
    Handler.token = args.token_file.read_text(encoding="utf-8").strip()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
