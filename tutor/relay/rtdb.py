# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A minimal async RTDB REST client: GET/PUT/PATCH/DELETE, ETags, server time.

Every call authenticates with ``?auth=<idToken>`` (RTDB REST has no header
form), so nothing here ever formats a URL or an ``httpx`` error into a
message or a log line: errors name the method, the path and the status only.
httpx's own request log (INFO, full URL) is silenced for the same reason.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import quote

import httpx

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

ROOT: Final = "tutor/v1"
SERVER_TIME: Final = {".sv": "timestamp"}
NULL_ETAG: Final = "null_etag"
_PRECONDITION_FAILED: Final = 412
_TIMEOUT: Final = httpx.Timeout(30.0, connect=15.0)
# The SSE read timeout: RTDB sends keep-alive every 30 s.
_STREAM_TIMEOUT: Final = httpx.Timeout(30.0, connect=15.0, read=75.0)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class RtdbError(RuntimeError):
    """A request failed; the message never contains the URL or the token."""


class ConflictError(RtdbError):
    """A conditional write lost the race (HTTP 412): the current value and ETag."""

    def __init__(self, path: str, value: object, etag: str) -> None:
        """Keep what the server holds now."""
        super().__init__(f"conditional write lost on {path}")
        self.value = value
        self.etag = etag


class Rtdb:
    """REST calls under ``/tutor/v1``; ``token`` yields a fresh id token."""

    def __init__(
        self,
        database_url: str,
        token: Callable[[], Awaitable[str]],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Bind the database; ``client`` is injectable (tests use a fake)."""
        self._base = database_url.rstrip("/")
        self._token = token
        self.client = client or httpx.AsyncClient(timeout=_TIMEOUT)

    def url(self, path: str) -> str:
        """The REST URL of ``path`` (relative to the tutor root), no token."""
        rel = "/".join(quote(p, safe="") for p in path.strip("/").split("/") if p)
        return f"{self._base}/{ROOT}/{rel}.json" if rel else f"{self._base}/{ROOT}.json"

    async def params(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Query parameters: the auth token plus ``extra``."""
        return {"auth": await self._token(), **(extra or {})}

    async def _call(
        self,
        method: str,
        path: str,
        *,
        value: object = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        kwargs: dict[str, Any] = {"params": await self.params(params)}
        if method in {"PUT", "PATCH"}:
            kwargs["content"] = json.dumps(value).encode()  # json=None sends no body
        try:
            response = await self.client.request(
                method, self.url(path), headers=headers or {}, **kwargs
            )
        except httpx.HTTPError as err:
            msg = f"{method} {path}: {type(err).__name__}"
            raise RtdbError(msg) from None
        if response.status_code == _PRECONDITION_FAILED:
            raise ConflictError(path, response.json(), response.headers.get("etag", ""))
        if response.is_error:
            msg = f"{method} {path}: HTTP {response.status_code}"
            raise RtdbError(msg)
        return response

    async def get(self, path: str, params: dict[str, str] | None = None) -> object:
        """The value at ``path`` (``None`` when absent)."""
        value: object = (await self._call("GET", path, params=params)).json()
        return value

    async def get_etag(self, path: str) -> tuple[Any, str]:
        """The value at ``path`` and its ETag (``null_etag`` when absent)."""
        response = await self._call("GET", path, headers={"X-Firebase-ETag": "true"})
        return response.json(), response.headers.get("etag", NULL_ETAG)

    async def put(self, path: str, value: object) -> object:
        """Write ``value``; returns it as stored (server timestamps resolved)."""
        stored: object = (await self._call("PUT", path, value=value)).json()
        return stored

    async def put_etag(
        self, path: str, value: object, if_match: str
    ) -> tuple[Any, str]:
        """A conditional PUT that also returns the new ETag."""
        headers = {"if-match": if_match, "X-Firebase-ETag": "true"}
        response = await self._call("PUT", path, value=value, headers=headers)
        return response.json(), response.headers.get("etag", "")

    async def patch(self, path: str, value: dict[str, Any]) -> None:
        """Merge ``value``'s children into ``path`` (``None`` children delete)."""
        await self._call("PATCH", path, value=value)

    async def delete(self, path: str, if_match: str | None = None) -> None:
        """Remove ``path``; with ``if_match`` only if unchanged."""
        headers = {"if-match": if_match} if if_match else {}
        await self._call("DELETE", path, headers=headers)

    async def open_stream(
        self, path: str, params: dict[str, str] | None = None
    ) -> AsyncIterator[str]:
        """The raw SSE lines of one connection to ``path`` (see ``sse``)."""
        request = self.client.build_request(
            "GET",
            self.url(path),
            params=await self.params(params),
            headers={"Accept": "text/event-stream"},
            timeout=_STREAM_TIMEOUT,
        )
        try:
            response = await self.client.send(request, stream=True)
        except httpx.HTTPError as err:
            msg = f"STREAM {path}: {type(err).__name__}"
            raise RtdbError(msg) from None
        try:
            if response.is_error:
                msg = f"STREAM {path}: HTTP {response.status_code}"
                raise RtdbError(msg)
            async for line in response.aiter_lines():
                yield line
        except httpx.HTTPError as err:
            msg = f"STREAM {path}: {type(err).__name__}"
            raise RtdbError(msg) from None
        finally:
            await response.aclose()

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
