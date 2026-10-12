# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The Flutter web client at ``/app/`` and its one-shot sign-in route.

The desktop app is this page in a Chrome ``--app`` window. The page cannot
run Google sign-in programmatically, and nothing outside the Chrome profile
can write its storage, so ``/app/sync-credentials`` hands it the PC's own
seeded Firebase session (``~/.config/tutor/firebase_auth.json``, written by
crdt-sync's ``link_google.py``) ONCE per server process; the page keeps it
from then on. It answers 404 once served, when the file is missing or
malformed, and to anything that is not a same-origin request on localhost
(a probe cannot tell which case it hit).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

from starlette.applications import Starlette
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from os import PathLike

    from starlette.requests import Request
    from starlette.types import Receive, Scope, Send

_logger = logging.getLogger(__name__)
WEB_DIR_ENV: Final = "TUTOR_WEBAPP_DIR"
CREDENTIALS_ENV: Final = "TUTOR_FIREBASE_AUTH"
# The build output: the repo's, or the copy tutor_deploy.sh puts in each release.
DEFAULT_WEB_DIR: Final = Path(__file__).resolve().parents[1] / "app" / "build" / "web"
_FIELDS: Final = ("id_token", "refresh_token", "expires_at")
_LOCAL_HOSTS: Final = frozenset({"127.0.0.1", "localhost", "[::1]"})
# Every file revalidates (ETag): a reload after a rebuild must never pair a
# cached bootstrap with a new main.dart.js.
_REVALIDATE: Final = {"Cache-Control": "no-cache"}
_NOT_BUILT: Final = (
    "The Tutor web app is not built. Run: "
    "cd app && fvm flutter build web --release --base-href /app/"
)


def web_dir_from_env() -> Path:
    """Where the built web app lives (``$TUTOR_WEBAPP_DIR`` or the repo)."""
    raw = os.environ.get(WEB_DIR_ENV, "")
    return Path(raw) if raw else DEFAULT_WEB_DIR


def credentials_from_env() -> Path:
    """The PC's seeded session file (``$TUTOR_FIREBASE_AUTH`` or ~/.config)."""
    raw = os.environ.get(CREDENTIALS_ENV, "")
    return (
        Path(raw) if raw else Path.home() / ".config" / "tutor" / "firebase_auth.json"
    )


def paths_from_env() -> tuple[Path, Path]:
    """(web dir, credentials file) for the live server."""
    return web_dir_from_env(), credentials_from_env()


class _Revalidated(StaticFiles):
    """Static files the browser must revalidate before every use."""

    def file_response(
        self,
        full_path: PathLike[str] | str,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        response.headers.update(_REVALIDATE)
        return response


class _WebApp:
    """Serves the build, or a 503 that says how to build it."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.files = _Revalidated(directory=directory, html=True, check_dir=False)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not (self.directory / "index.html").is_file():
            await PlainTextResponse(_NOT_BUILT, status_code=503)(scope, receive, send)
            return
        await self.files(scope, receive, send)


def read_credentials(path: Path) -> dict[str, str] | None:
    """The session in ``path`` if it has every field as a string, else None."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        _logger.warning("no usable seeded session at %s", path, exc_info=True)
        return None
    if not isinstance(data, dict) or not all(
        isinstance(data.get(k), str) for k in _FIELDS
    ):
        _logger.warning("seeded session at %s lacks %s", path, ", ".join(_FIELDS))
        return None
    return {k: data[k] for k in _FIELDS}


def _same_origin_local(request: Request) -> bool:
    """A request from the page itself, on this machine."""
    host = request.headers.get("host", "").rsplit(":", 1)[0]
    site = request.headers.get("sec-fetch-site", "same-origin")
    return host in _LOCAL_HOSTS and site in {"same-origin", "none"}


def webapp_routes(web_dir: Path, credentials: Path) -> list[BaseRoute]:
    """``/app`` -> ``/app/``, the one-shot credentials route, the build."""
    served = False

    async def sync_credentials(request: Request) -> Response:
        nonlocal served
        body = (
            None
            if served or not _same_origin_local(request)
            else read_credentials(credentials)
        )
        if body is None:
            return Response(status_code=404)
        served = True
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    async def to_slash(_: Request) -> Response:
        return RedirectResponse("/app/", status_code=308)

    return [
        Route("/app", to_slash),
        Route("/app/sync-credentials", sync_credentials),
        Mount("/app", app=_WebApp(web_dir)),
    ]


def standalone_app() -> Starlette:
    """Only the web app (dev and screenshot runs; no engine, no ledger).

    ``uvicorn --factory tutor.webapp:standalone_app --port 8791``
    """
    return Starlette(routes=webapp_routes(*paths_from_env()))
