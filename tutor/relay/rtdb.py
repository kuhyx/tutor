# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's RTDB REST client: ``rtdb_relay``'s, rooted at ``tutor/v1-e2e``.

Under ``tutor/v1-e2e`` every value goes through ``e2e.Sealer`` (sealed on
write, opened on read) once ``sealer`` is set; ``at()`` gives the raw
client the e2e header and the one-time copy use. Errors never carry the URL
or the token (see ``rtdb_relay.rtdb``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from rtdb_relay import rtdb as _base
from rtdb_relay.rtdb import NULL_ETAG, SERVER_TIME, ConflictError, RtdbError

from tutor.relay import e2e

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import httpx
    from rtdb_relay.seal import Sealer

__all__ = ["NULL_ETAG", "ROOT", "SERVER_TIME", "ConflictError", "Rtdb", "RtdbError"]

ROOT: Final = e2e.ROOT


def within(namespace: str, root: str) -> str:
    """``root`` under ``namespace`` (unchanged without one, or if already under it)."""
    if not namespace or root == namespace or root.startswith(f"{namespace}/"):
        return root
    return f"{namespace}/{root}".rstrip("/")


class Rtdb(_base.Rtdb):
    """REST calls under ``/tutor/v1-e2e``; ``token`` yields a fresh id token.

    ``namespace`` (``sandbox/slotN``, set by :meth:`under`) moves the root and
    every raw ``at()`` client under ``/<namespace>/``, as a slot APK's
    ``SYNC_NAMESPACE`` does on the phone; "" is the live tree.
    """

    namespace: str = ""

    def __init__(
        self,
        database_url: str,
        token: Callable[[], Awaitable[str]],
        client: httpx.AsyncClient | None = None,
        *,
        root: str = ROOT,
        sealer: Sealer | None = None,
    ) -> None:
        """Bind the database; ``client`` is injectable (tests use a fake)."""
        super().__init__(database_url, token, client, root=root, sealer=sealer)

    @classmethod
    def under(
        cls,
        namespace: str,
        database_url: str,
        token: Callable[[], Awaitable[str]],
    ) -> Rtdb:
        """A client rooted at ``<namespace>/tutor/v1-e2e`` (validated by the caller)."""
        db = cls(database_url, token, root=within(namespace, ROOT))
        db.namespace = namespace
        return db

    def at(self, root: str) -> Rtdb:
        """A raw (unsealed) client on ``root``, inside this one's namespace."""
        db = type(self)(
            self._base, self._token, self.client, root=within(self.namespace, root)
        )
        db.namespace = self.namespace
        return db
