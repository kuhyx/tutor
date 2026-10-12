# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""An in-memory Firebase RTDB behind ``httpx.MockTransport``.

REST semantics the relay relies on: GET (shallow, orderBy/startAt), PUT,
PATCH, DELETE, ``X-Firebase-ETag`` / ``if-match`` with 412 + current value,
``{".sv": "timestamp"}``, ``?auth=`` checking, and SSE streams (initial put,
put/patch events, keep-alive, auth_revoked, cancel, drop).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import TYPE_CHECKING, Any

import httpx

from tutor.relay.rtdb import Rtdb

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

AUTH = "test-token"
DB = "https://db.test"


def _parts(path: str) -> list[str]:
    return [p for p in path.strip("/").split("/") if p]


def etag(value: object) -> str:
    if value is None:
        return "null_etag"
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class FakeRtdb:
    """The database; ``now_ms`` resolves server timestamps."""

    def __init__(self, now_ms: int = 1_800_000_000_000) -> None:
        self.root: dict[str, Any] = {}
        self.now_ms = now_ms
        self.streams: list[tuple[list[str], asyncio.Queue[str | None]]] = []
        self.fail: dict[tuple[str, str], int] = {}  # (method, rel path) -> status
        self.raise_on: set[tuple[str, str]] = set()  # -> httpx.ConnectError
        self.log: list[tuple[str, str]] = []
        self.token = AUTH

    # -- tree -----------------------------------------------------------------
    def get(self, path: str) -> Any:
        node: Any = self.root
        for part in _parts(path):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def _sv(self, value: Any) -> Any:
        if value == {".sv": "timestamp"}:
            return self.now_ms
        if isinstance(value, dict):
            out = {k: self._sv(v) for k, v in value.items()}
            return {k: v for k, v in out.items() if v is not None} or None
        return value

    def set(self, path: str, value: Any) -> None:
        parts = _parts(path)
        value = self._sv(value)
        if not parts:
            self.root = value if isinstance(value, dict) else {}
            return
        node = self.root
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        if value is None:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value
        self.root = _prune(self.root) or {}

    # -- streams --------------------------------------------------------------
    def _notify(self, kind: str, path: str, data: Any) -> None:
        where = _parts(path)
        for listen, queue in self.streams:
            if where[: len(listen)] == listen:
                rel = "/" + "/".join(where[len(listen) :])
                queue.put_nowait(_event(kind, rel, data))
            elif listen[: len(where)] == where:
                queue.put_nowait(_event("put", "/", self.get("/".join(listen))))

    def push(self, raw: str | None) -> None:
        """Send a raw SSE block (or ``None``: close) to every stream."""
        for _, queue in self.streams:
            queue.put_nowait(raw)

    # -- HTTP -----------------------------------------------------------------
    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    def rtdb(self) -> Rtdb:
        async def token() -> str:
            return self.token

        return Rtdb(DB, token, client=self.client())

    async def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removesuffix(".json").removeprefix("/tutor/v1")
        method = request.method
        self.log.append((method, path))
        if (method, path) in self.raise_on:
            msg = "boom"
            raise httpx.ConnectError(msg, request=request)
        if request.url.params.get("auth") != AUTH:
            return _reply(401, {"error": "Permission denied"})
        if (method, path) in self.fail:
            return _reply(self.fail[(method, path)], {"error": "x"})
        full = f"tutor/v1{path}"
        if request.headers.get("accept") == "text/event-stream":
            return self._stream(full)
        current = self.get(full)
        match = request.headers.get("if-match")
        if match is not None and match != etag(current):
            return _reply(412, current, headers={"ETag": etag(current)})
        if method == "GET":
            return self._get(request, full, current)
        return self._write(method, full, request)

    def _write(self, method: str, full: str, request: httpx.Request) -> httpx.Response:
        if method == "PUT":
            self.set(full, json.loads(request.content))
            self._notify("put", full, self.get(full))
            stored = self.get(full)
            return _reply(200, stored, headers={"ETag": etag(stored)})
        if method == "PATCH":
            body = json.loads(request.content)
            for key, value in body.items():
                self.set(f"{full}/{key}", value)
            self._notify("patch", full, self._sv(body))
            return _reply(200, body)
        self.set(full, None)  # DELETE
        self._notify("put", full, None)
        return _reply(200, None)

    def _get(self, request: httpx.Request, full: str, value: Any) -> httpx.Response:
        params = request.url.params
        if params.get("shallow") == "true" and isinstance(value, dict):
            value = dict.fromkeys(value, True)
        start = params.get("startAt")
        if start and isinstance(value, dict):
            value = {k: v for k, v in value.items() if k >= json.loads(start)}
        headers = (
            {"ETag": etag(value)} if request.headers.get("x-firebase-etag") else {}
        )
        return _reply(200, value, headers=headers)

    def _stream(self, full: str) -> httpx.Response:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        entry = (_parts(full), queue)
        self.streams.append(entry)
        queue.put_nowait(_event("put", "/", self.get(full)))

        async def body() -> AsyncIterator[bytes]:
            try:
                while (block := await queue.get()) is not None:
                    yield block.encode()
            finally:
                self.streams.remove(entry)

        return httpx.Response(
            200, content=body(), headers={"content-type": "text/event-stream"}
        )


def _event(kind: str, path: str, data: Any) -> str:
    return f"event: {kind}\ndata: {json.dumps({'path': path, 'data': data})}\n\n"


def _prune(node: Any) -> Any:
    """RTDB keeps no empty objects."""
    if not isinstance(node, dict):
        return node
    out = {k: _prune(v) for k, v in node.items()}
    return {k: v for k, v in out.items() if v is not None and v != {}} or None


def _reply(
    status: int, value: Any, headers: dict[str, str] | None = None
) -> httpx.Response:
    """A JSON response; ``httpx.Response(json=None)`` would send no body at all."""
    return httpx.Response(
        status, content=json.dumps(value).encode(), headers=headers or {}
    )
