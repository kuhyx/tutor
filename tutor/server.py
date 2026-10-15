# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The local server: a small Starlette app bound to 127.0.0.1 only.

``/`` redirects to the Flutter client at ``/app/`` (``tutor.webapp``). The
JSON routes left are the ones scripts drive over HTTP: ``tutor.scripted``
(start, message, stop), the deploy smoke test and ``run.sh`` (state). The
phone and the desktop app talk to the engine over the RTDB relay instead.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import re
import traceback
from typing import TYPE_CHECKING, Any, Final

from claude_agent_sdk import ClaudeSDKError
from starlette.applications import Starlette
from starlette.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Route

from tutor import delivery, diagrams, images, webapp
from tutor.engine import Engine
from tutor.outage import ClaudeUnavailableError
from tutor.session import SessionError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Coroutine
    from pathlib import Path

    from starlette.requests import Request

_logger = logging.getLogger(__name__)
_SAFE_NAME: Final = re.compile(r"^[0-9a-f]{16}(-\d)?\.(png|jpg|svg)$")


def create_app(
    engine: Engine | None = None,
    *,
    media_dirs: tuple[Path, Path] | None = None,
) -> Starlette:
    """Build the app; the engine and the media dirs are injectable."""
    eng = engine or Engine()
    image_dir, diagram_dir = media_dirs or (images.cache_dir(), diagrams.cache_dir())

    async def index(_: Request) -> Response:
        # Temporary: a browser must not cache where `/` points.
        return RedirectResponse("/app/", status_code=307)

    async def state(_: Request) -> Response:
        return JSONResponse(eng.state())

    async def start(request: Request) -> Response:
        body = await _json(request)
        return await _guard(eng.start(body.get("card_id")))

    async def message(request: Request) -> Response:
        args = _reply_args(await _json(request))
        if isinstance(args, Response):
            return args
        return await _guard(eng.reply(*args))

    async def stop(_: Request) -> Response:
        return await _guard(eng.stop())

    async def media(request: Request) -> Response:
        name = request.path_params["name"]
        if not _SAFE_NAME.match(name):
            return Response(status_code=404)
        folder = diagram_dir if name.endswith(".svg") else image_dir
        path = folder / name
        return FileResponse(path) if path.is_file() else Response(status_code=404)

    routes = [
        Route("/", index),
        Route("/api/state", state),
        Route("/api/start", start, methods=["POST"]),
        Route("/api/message", message, methods=["POST"]),
        Route("/api/stop", stop, methods=["POST"]),
        Route("/media/{name}", media),
        # The Flutter client (desktop: Chrome --app window).
        *webapp.webapp_routes(*webapp.paths_from_env()),
    ]

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        yield
        await eng.close()

    # Anything no route maps itself still reaches the caller as JSON
    # (Starlette's ServerErrorMiddleware runs this, then re-raises so uvicorn
    # logs the traceback): typed handlers below, this net for the rest.
    app = Starlette(
        routes=routes, lifespan=lifespan, exception_handlers={Exception: _unhandled}
    )
    app.state.engine = eng
    return app


async def _json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError as err:
        _logger.warning("%s body is not JSON: %s", request.url.path, err)
        return {}
    return body if isinstance(body, dict) else {}


def _reply_args(
    body: dict[str, Any],
) -> tuple[str, float, str, delivery.Delivery] | Response:
    """``Engine.reply``'s arguments from a message body, or the 400 refusing it.

    ``sent_at`` counts only when numeric; ``device`` is phone or desktop.
    """
    text = str(body.get("text", "")).strip()
    if not text:
        return JSONResponse({"error": "empty message"}, status_code=400)
    try:
        device = delivery.device(body.get("device"))
    except ValueError as err:
        _logger.warning("message refused: %s", err)
        return JSONResponse({"error": str(err)}, status_code=400)
    sent = body.get("sent_at")
    sent_at = float(sent) if isinstance(sent, (int, float)) else None
    msg_id = str(body.get("msg_id", ""))[:64]
    advance = float(body.get("advance_s", 0))
    return text, advance, msg_id, delivery.Delivery(sent_at, device=device)


async def _guard(call: Coroutine[Any, Any, dict[str, Any]]) -> Response:
    try:
        return JSONResponse(await call)
    except ClaudeUnavailableError as err:  # the relay's claude_unavailable, as a 503
        _logger.warning("Claude unavailable: %s", err)
        body = {**_error_body(err), "code": "claude_unavailable", **err.fields()}
        return JSONResponse(body, status_code=503)
    except (
        SessionError,
        ClaudeSDKError,
        ValueError,
        RuntimeError,
        TimeoutError,
    ) as err:
        _logger.warning("tutor call failed: %s", err)
        return JSONResponse(_error_body(err), status_code=502)


async def _unhandled(_: Request, err: Exception) -> Response:
    """Any error no route maps: a 500 whose body carries the traceback."""
    _logger.error("unhandled tutor error: %s", err)
    return JSONResponse(_error_body(err), status_code=500)


def _error_body(err: BaseException) -> dict[str, str]:
    """Error JSON with the traceback: bound to 127.0.0.1, so only kuhy sees it."""
    return {
        "error": str(err) or type(err).__name__,
        "type": type(err).__name__,
        "traceback": "".join(traceback.format_exception(err)),
    }
