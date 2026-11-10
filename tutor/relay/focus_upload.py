# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A rules screenshot arrives as chunks in ``uploads/{ulid}``, not in a request.

The ``requests/`` node is mirrored whole over SSE and kept for a day, so an
image never rides in it. The client writes ``uploads/{ulid}/c0001..cNNNN``
(base64 text, <= ``MAX_CHUNK`` characters each) and then sends a small
``focus_evidence`` request naming the upload, its chunk count, the sha256 of
the decoded bytes and the mime type. The worker reads the chunks, checks all
of that plus the file's magic bytes, and always deletes the node afterwards.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
from typing import TYPE_CHECKING, Any, Final, NoReturn

from tutor.relay.errors import RequestError
from tutor.relay.rtdb import RtdbError

if TYPE_CHECKING:
    from collections.abc import Callable

    from tutor.relay.rtdb import Rtdb

MAX_CHUNK: Final = 262_144
# mime -> (file suffix, magic check)
_MAGIC: Final[dict[str, tuple[str, Callable[[bytes], bool]]]] = {
    "image/png": (".png", lambda b: b.startswith(b"\x89PNG\r\n\x1a\n")),
    "image/jpeg": (".jpg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "image/webp": (".webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
}
_logger = logging.getLogger(__name__)


def _bad(why: str) -> NoReturn:
    msg = f"focus_evidence: {why}"
    raise RequestError(msg, code="bad_request")


def _decode(node: object, body: dict[str, Any]) -> bytes:
    """The verified bytes of ``node``; ``bad_request`` for anything off."""
    if not isinstance(node, dict):
        _bad("the upload is missing")
    texts = [node.get(f"c{n:04d}") for n in range(1, body["chunks"] + 1)]
    chunks = [t for t in texts if isinstance(t, str) and 0 < len(t) <= MAX_CHUNK]
    if len(chunks) != len(texts):
        _bad("the upload is incomplete or a chunk is too long")
    try:
        data = base64.b64decode("".join(chunks), validate=True)
    except binascii.Error as exc:
        _logger.warning("upload %s is not base64: %s", body["upload"], exc)
        _bad("the upload is not base64")
    if hashlib.sha256(data).hexdigest() != body["sha256"]:
        _bad("the upload does not match its sha256")
    if not _MAGIC[body["mime"]][1](data):
        _bad(f"the upload is not a {body['mime']} file")
    return data


async def fetch(rtdb: Rtdb, body: dict[str, Any]) -> tuple[bytes, str]:
    """``(bytes, suffix)`` of the upload ``body`` names; the node is deleted after."""
    missing = [k for k in ("upload", "chunks", "sha256", "mime") if body[k] is None]
    if missing:
        _bad(f"a file needs {', '.join(missing)}")
    path = f"uploads/{body['upload']}"
    try:
        node = await rtdb.get(path)
    except RtdbError as exc:
        msg = f"the upload could not be read: {exc}"
        raise RequestError(msg, code="worker_error", retry=True) from exc
    try:
        return _decode(node, body), _MAGIC[body["mime"]][0]
    finally:
        try:
            await rtdb.delete(path)
        except RtdbError as exc:
            _logger.warning("upload %s not deleted: %s", body["upload"], exc)
