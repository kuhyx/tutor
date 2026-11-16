# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""End-to-end encryption of the tutor's RTDB tree (DOCS-contract §12).

The tree keeps its shape: keys (ids, slugs, ``m0001``) stay clear so
``orderBy="$key"``, PATCH and SSE paths work unchanged. Every *unit* (a
node one writer writes whole, below which nothing is written) is stored as
``{"_e2e": <XChaCha20-Poly1305 blob>, <clear siblings>}``; the blob is
crdt_sync's ``E2eCipher`` with the unit's full path as AAD, under the
Argon2id key of the shared crdt-sync password (header at ``tutor/e2e``).
Clear siblings are only server timestamps the credit maths needs resolved
by RTDB (``req.created``, ``result.at``, presence beats). ``meta``, ``rev``,
the request ``claim`` and ``progress/rid`` hold ids, counters and lease
times only and stay clear. A write to any other path is refused (fail
closed), so a new node cannot go out in plaintext by accident.

``tests/../contract/e2e_vectors.json`` pins the format for the Flutter side.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

from crdt_sync import Argon2Params, E2eCipher, E2eKey, E2eLayout
from rtdb_relay import unlock as _unlock
from rtdb_relay.layout import E2eLayoutError, Layout, Rule, parts_of
from rtdb_relay.seal import SEALED
from rtdb_relay.seal import Sealer as _Sealer

from tutor.history import SESSION_ID

if TYPE_CHECKING:
    from rtdb_relay.rtdb import Rtdb

__all__ = [
    "LAYOUT",
    "ROOT",
    "SEALED",
    "E2eLayoutError",
    "Rule",
    "Sealer",
    "classify",
    "migrate",
    "parts_of",
    "unit_path",
    "unlock",
]

OLD_ROOT: Final = "tutor/v1"
LAYOUT: Final = E2eLayout.of(OLD_ROOT)
ROOT: Final = LAYOUT.prefix  # tutor/v1-e2e
# Raised in the old root once the copy ran: a pre-e2e client refuses to run
# there instead of writing into a prefix nobody reads any more.
MIN_CLIENT: Final = 2
MIGRATED: Final = "migration/v1_copied_at"
_PATCH_CHUNK: Final = 200

RULES: Final = Layout(
    root=ROOT,
    clear=(
        "meta",
        "rev",
        "migration",
        "requests/*/claim",
        "sessions/*/progress/rid",
    ),
    units={
        "live": frozenset(),
        "prefs/*": frozenset(),
        "stats/*": frozenset(),
        "presence/workers/*": frozenset({"beat"}),
        "presence/clients/*": frozenset({"seen"}),
        "uploads/*/*": frozenset(),
        "requests/*/req": frozenset({"created"}),
        "requests/*/result": frozenset({"at"}),
        "sessions/*/meta/*": frozenset(),
        "sessions/*/msgs/*": frozenset(),
        "sessions/*/receipts/*": frozenset(),
        "sessions/*/user/*": frozenset(),
        "sessions/*/progress/steps/*": frozenset(),
        "session_index/*": frozenset(),
        "subjects/*/meta": frozenset(),
        "subjects/*/plan": frozenset(),
        "subjects/*/cards": frozenset(),
        "subjects/*/concepts": frozenset(),
        "log/*/*": frozenset(),
        "feedback/*": frozenset(),
    },
)

_logger = logging.getLogger(__name__)


def classify(parts: list[str]) -> Rule:
    """The rule for the node at ``parts`` (relative to :data:`ROOT`)."""
    return RULES.classify(parts)


def unit_path(path: str) -> str | None:
    """The sealed unit ``path`` lies strictly below, or ``None``."""
    return RULES.unit_path(path)


class Sealer(_Sealer):
    """The tutor's sealer: :data:`RULES` under ``root``."""

    def __init__(self, cipher: E2eCipher, root: str = ROOT) -> None:
        """Use ``cipher`` (the key's) for every unit under ``root``."""
        super().__init__(cipher, RULES, root)


async def unlock(
    rtdb: Rtdb, passphrase: str, params: Argon2Params | None = None
) -> E2eKey:
    """The tutor's key from the shared passphrase (header made on first use).

    Raises:
        E2eLockedError: No passphrase, a wrong one, or an unreadable header.
    """
    return await _unlock.unlock(rtdb, passphrase, LAYOUT, params)


# -- the one-time copy ----------------------------------------------------------
def _flat(node: object, depth: int, prefix: str = "") -> dict[str, Any]:
    """``{"a/b": value}`` of ``node``'s entries ``depth`` levels down."""
    if depth == 0:
        return {prefix: node} if node is not None else {}
    if not isinstance(node, dict):
        return {}
    out: dict[str, Any] = {}
    for key, child in node.items():
        out.update(_flat(child, depth - 1, f"{prefix}/{key}" if prefix else key))
    return out


async def _copy(old: Rtdb, new: Rtdb, path: str, depth: int) -> int:
    """PATCH into ``new`` every entry of ``old`` at ``path`` it lacks."""
    have = _flat(await new.get(path), depth)
    missing = {
        k: v for k, v in _flat(await old.get(path), depth).items() if k not in have
    }
    keys = sorted(missing)
    for i in range(0, len(keys), _PATCH_CHUNK):
        await new.patch(path, {k: missing[k] for k in keys[i : i + _PATCH_CHUNK]})
    return len(missing)


async def migrate(rtdb: Rtdb) -> int:
    """Copy the client-owned nodes of ``tutor/v1`` once; never deletes them.

    Only RTDB-canonical data is copied (DOCS-contract §1): ``log``,
    ``prefs``, ``feedback`` and each session's ``user``. The worker
    re-publishes projections from its own files; requests, presence,
    ``live`` and uploads are transient. Old clients are fenced first
    (``meta.min_client``), then entries missing in the new root are
    patched in, so a rerun after a crash copies only the rest.
    """
    if await rtdb.get(MIGRATED) is not None:
        return 0
    old = rtdb.at(OLD_ROOT)
    await old.put("meta/min_client", MIN_CLIENT)
    copied = 0
    for path, depth in (("log", 2), ("prefs", 1), ("feedback", 1)):
        copied += await _copy(old, rtdb, path, depth)
    sids = await old.get("sessions", {"shallow": "true"})
    for sid in sorted(sids) if isinstance(sids, dict) else []:
        if not SESSION_ID.fullmatch(sid):
            continue  # untrusted key: never part of a path (§10)
        copied += await _copy(old, rtdb, f"sessions/{sid}/user", 1)
    await rtdb.put(MIGRATED, {".sv": "timestamp"})
    _logger.warning("e2e: copied %d node(s) from %s", copied, OLD_ROOT)
    return copied
