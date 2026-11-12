#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The agent-E2E sandbox's e2e passphrase and a sealed view of the emulator.

Never the real crdt-sync password: the sandbox has its own, and the emulator
its own header (cheap Argon2id, made by ``e2e_server.py``'s seed). The web
build (``app/tool/e2e/main.dart``) stores the same passphrase.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final
import urllib.request

from crdt_sync import Argon2Params, E2eKey, unlock_e2e

from tutor.relay import e2e

if TYPE_CHECKING:
    from collections.abc import Callable

SANDBOX_PASSPHRASE: Final = "e2e-sandbox-passphrase"
SANDBOX_ARGON: Final = Argon2Params(memory_kib=8, iterations=1, parallelism=1)


class _Header:
    """crdt_sync's sync ``RemoteStore``, the header subset, over urllib."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def get_file_text(self, path: str) -> str | None:
        with urllib.request.urlopen(f"{self.url}/{path}.json", timeout=10) as r:
            value = json.load(r)
        return value if value is None or isinstance(value, str) else json.dumps(value)

    def list_directory(self, path: str) -> list[str]:
        """Nothing: only the header is read through here."""
        del path
        return []

    def delete_file(self, path: str, *, message: str = "") -> None:
        """Refused: the header is never deleted."""
        del path, message
        msg = "the sandbox never deletes the e2e header"
        raise NotImplementedError(msg)

    def can_access_remote(self) -> bool:
        """Always (a loopback emulator)."""
        return True

    def put_file_text(self, path: str, text: str, *, message: str) -> None:
        del message
        req = urllib.request.Request(
            f"{self.url}/{path}.json", data=json.dumps(text).encode(), method="PUT"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()


def sandbox_key(url: str) -> E2eKey:
    """The sandbox key from the emulator's header (made on first use)."""
    return unlock_e2e(
        _Header(url),
        path_prefix=e2e.LAYOUT.prefix,
        passphrase=SANDBOX_PASSPHRASE,
        params=SANDBOX_ARGON,
        e2e_path=e2e.LAYOUT.e2e_path,
    )


def opened(sealer: e2e.Sealer, path: str, fetch: Callable[[str], object]) -> object:
    """``fetch(path)`` opened; below a unit the unit is fetched and walked."""
    unit = e2e.unit_path(path)
    if unit is None:
        return sealer.open(path, fetch(path))
    node: Any = sealer.open(unit, fetch(unit))
    for part in e2e.parts_of(path)[len(e2e.parts_of(unit)) :]:
        node = node.get(part) if isinstance(node, dict) else None
    return node
