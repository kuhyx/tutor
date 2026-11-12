# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Where the relay connects and as whom: all of it from ``~/.config``, none in git.

The database URL and API key come from crdt-sync's shared
``~/.config/crdt-sync/firebase.json``; the signed-in session is the
``tutor`` app's own, ``~/.config/tutor/firebase_auth.json`` (seeded once with
crdt-sync ``python3 -m tool.seed_session --app tutor``). Never
``firebase_client_for``: without a session it falls back to the dead shared
password and fails with a misleading error.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Final

from crdt_sync import (
    ConfigError,
    E2eLockedError,
    FirebaseAuthError,
    FirebaseConfig,
    FirebaseTokenProvider,
    credential_store_for,
    load_device_identity,
)

from tutor.relay import e2e
from tutor.relay.rtdb import Rtdb, RtdbError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from crdt_sync import Argon2Params

APP: Final = "tutor"
_logger = logging.getLogger(__name__)


class RelaySetupError(RuntimeError):
    """The relay cannot start: no config or no signed-in session."""


def token_source(provider: FirebaseTokenProvider) -> Callable[[], Awaitable[str]]:
    """An async id-token getter (the provider is sync and refreshes itself)."""

    async def token() -> str:
        try:
            return await asyncio.to_thread(provider.id_token)
        except FirebaseAuthError as err:
            msg = f"firebase auth failed: {err}"
            raise RtdbError(msg) from None

    return token


def connect() -> Rtdb:
    """The tutor's RTDB client, signed in as the ``tutor`` app."""
    try:
        config = FirebaseConfig.load()
    except ConfigError as err:
        msg = f"no crdt-sync firebase config: {err}"
        raise RelaySetupError(msg) from err
    provider = FirebaseTokenProvider(config.api_key, credential_store_for(APP))
    if not provider.has_session():
        msg = (
            "no signed-in session in ~/.config/tutor/firebase_auth.json; seed it "
            "with crdt-sync: python3 -m tool.seed_session ... --app tutor"
        )
        raise RelaySetupError(msg)
    return Rtdb(config.database_url, token_source(provider))


def device_id(data_dir: Path) -> str:
    """This worker's persisted uuid4 (``<data>/device_id``)."""
    identity = load_device_identity(data_dir / "device_id")
    return str(identity.device_id)


def password_file() -> Path:
    """``~/.config/crdt-sync/password``, resolved now (tests move HOME)."""
    return Path.home() / ".config" / "crdt-sync" / "password"


def read_passphrase(path: Path) -> str:
    """The password stored in ``path``, or "" when there is none (locked)."""
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as err:
        _logger.warning("cannot read %s (%s): e2e stays locked", path, err)
        return ""


def passphrase() -> str:
    """The shared crdt-sync password of this PC (crdt_sync's ``PASSWORD_FILE``)."""
    return read_passphrase(password_file())


async def seal(rtdb: Rtdb, secret: str, params: Argon2Params | None = None) -> Rtdb:
    """Unlock the e2e key on ``rtdb``; it seals everything it writes from now on.

    Raises:
        E2eLockedError: No, or a wrong, passphrase: nothing may be read or
            written (fail closed).
        RtdbError: The header could not be read or written.
    """
    key = await e2e.unlock(rtdb, secret, params)
    rtdb.sealer = e2e.Sealer(key.cipher())
    return rtdb


async def connect_sealed(secret: str | None = None) -> Rtdb:
    """:func:`connect` and :func:`seal` (one-shot commands; no retry).

    Raises:
        RelaySetupError: No session, or the e2e key is locked.
    """
    rtdb = connect()
    try:
        return await seal(rtdb, passphrase() if secret is None else secret)
    except (E2eLockedError, RtdbError) as err:
        await rtdb.aclose()
        msg = f"e2e locked or unreachable ({err}); see {password_file()}"
        raise RelaySetupError(msg) from err
