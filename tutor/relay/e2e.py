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

import asyncio
from dataclasses import dataclass
import json
import logging
from typing import TYPE_CHECKING, Any, Final

from crdt_sync import (
    Argon2Params,
    E2eCipher,
    E2eDecryptError,
    E2eHeaderError,
    E2eKey,
    E2eLayout,
    E2eLockedError,
    E2eWrongPassphraseError,
    unlock_e2e,
)

from tutor.history import SESSION_ID

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from tutor.relay.rtdb import Rtdb

OLD_ROOT: Final = "tutor/v1"
LAYOUT: Final = E2eLayout.of(OLD_ROOT)
ROOT: Final = LAYOUT.prefix  # tutor/v1-e2e
SEALED: Final = "_e2e"
# Raised in the old root once the copy ran: a pre-e2e client refuses to run
# there instead of writing into a prefix nobody reads any more.
MIN_CLIENT: Final = 2
MIGRATED: Final = "migration/v1_copied_at"
_PATCH_CHUNK: Final = 200

_CLEAR: Final = (
    "meta",
    "rev",
    "migration",
    "requests/*/claim",
    "sessions/*/progress/rid",
)
_UNITS: Final[dict[str, frozenset[str]]] = {
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
}

_logger = logging.getLogger(__name__)


class E2eLayoutError(ValueError):
    """A write the layout has no rule for, or one below a sealed unit."""


def parts_of(path: str) -> list[str]:
    """``path``'s segments (no empty ones)."""
    return [p for p in path.split("/") if p]


def _matches(pattern: list[str], parts: list[str]) -> bool:
    return len(pattern) == len(parts) and all(
        p in {"*", q} for p, q in zip(pattern, parts, strict=True)
    )


@dataclass(frozen=True)
class Rule:
    """Where ``parts`` falls: ``clear``, ``unit``, ``below``, ``struct``, ``unknown``.

    ``depth`` is the unit's length for ``below``; ``keep`` the clear fields
    of a unit.
    """

    kind: str
    depth: int = 0
    keep: frozenset[str] = frozenset()


def classify(parts: list[str]) -> Rule:
    """The rule for the node at ``parts`` (relative to :data:`ROOT`)."""
    for pattern in _CLEAR:
        pat = pattern.split("/")
        if len(pat) <= len(parts) and _matches(pat, parts[: len(pat)]):
            return Rule("clear")
    for pattern, keep in _UNITS.items():
        pat = pattern.split("/")
        if _matches(pat, parts):
            return Rule("unit", len(pat), keep)
        if len(pat) < len(parts) and _matches(pat, parts[: len(pat)]):
            return Rule("below", len(pat), keep)
    for pattern in (*_CLEAR, *_UNITS):
        pat = pattern.split("/")
        if len(parts) < len(pat) and _matches(pat[: len(parts)], parts):
            return Rule("struct")
    return Rule("unknown")


def _pruned(value: object) -> object:
    """``value`` as RTDB would keep it: no null members, no empty objects."""
    if not isinstance(value, dict):
        return value
    out = {k: _pruned(v) for k, v in value.items()}
    return {k: v for k, v in out.items() if v is not None} or None


def _dumps(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class Sealer:
    """Seals writes and opens reads of the tree under ``root``."""

    def __init__(self, cipher: E2eCipher, root: str = ROOT) -> None:
        """Use ``cipher`` (the key's) for every unit under ``root``."""
        self._cipher = cipher
        self.root = root

    def _aad(self, parts: list[str]) -> str:
        return "/".join([self.root, *parts])

    # -- writes ---------------------------------------------------------------
    def seal(self, path: str, value: object) -> object:
        """``value`` as it may be stored at ``path``; refuses unknown paths."""
        return self._seal(parts_of(path), value)

    def seal_patch(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """A PATCH body for ``path``: each (multi-segment) key sealed on its own."""
        if classify(parts_of(path)).kind in {"unit", "below"}:
            msg = f"PATCH into sealed unit {path}"
            raise E2eLayoutError(msg)
        base = parts_of(path)
        return {k: self._seal([*base, *parts_of(k)], v) for k, v in body.items()}

    def _seal(self, parts: list[str], value: object) -> object:
        rule = classify(parts)
        if rule.kind == "clear" or value is None:
            return value
        if rule.kind == "unit":
            return self._seal_unit(parts, value, rule.keep)
        if rule.kind == "struct" and isinstance(value, dict):
            return {k: self._seal([*parts, *parts_of(k)], v) for k, v in value.items()}
        where = "/".join(parts) or "/"
        msg = f"no e2e rule for a {type(value).__name__} at {where} ({rule.kind})"
        raise E2eLayoutError(msg)

    def _seal_unit(
        self, parts: list[str], value: object, keep: frozenset[str]
    ) -> object:
        value = _pruned(value)
        if value is None:
            return None  # RTDB stores no null and no empty object
        clear: dict[str, Any] = {}
        if isinstance(value, dict) and keep:
            clear = {k: v for k, v in value.items() if k in keep}
            value = {k: v for k, v in value.items() if k not in keep}
        blob = self._cipher.seal(_dumps(value), path=self._aad(parts))
        return {SEALED: blob, **clear}

    # -- reads ----------------------------------------------------------------
    def open(self, path: str, value: object) -> object:
        """``value`` read at ``path``, every unit in it opened.

        A unit that does not open (tampered, other key) reads as absent.
        Legacy plaintext (a unit without ``_e2e``) is returned as stored.
        """
        return self._open(parts_of(path), value)

    def _open(self, parts: list[str], value: object) -> object:
        rule = classify(parts)
        if rule.kind == "unit":
            return self._open_unit(parts, value)
        if rule.kind == "below":
            msg = f"read below sealed unit: {'/'.join(parts)}"
            raise E2eLayoutError(msg)
        if rule.kind == "struct" and isinstance(value, dict):
            out = {k: self._open([*parts, k], v) for k, v in value.items()}
            return {k: v for k, v in out.items() if v is not None}
        if rule.kind == "struct" and isinstance(value, list):
            return [self._open([*parts, str(i)], v) for i, v in enumerate(value)]
        return value

    def _open_unit(self, parts: list[str], value: object) -> object:
        if not isinstance(value, dict) or not isinstance(value.get(SEALED), str):
            return value  # legacy plaintext, accepted during the migration
        clear = {k: v for k, v in value.items() if k != SEALED}
        try:
            text = self._cipher.open(value[SEALED], path=self._aad(parts))
            data = json.loads(text)
        except E2eDecryptError, ValueError:
            _logger.warning("undecryptable node %s dropped", "/".join(parts))
            return None
        return {**data, **clear} if isinstance(data, dict) else data


def unit_path(path: str) -> str | None:
    """The sealed unit ``path`` lies strictly below, or ``None``."""
    parts = parts_of(path)
    rule = classify(parts)
    return "/".join(parts[: rule.depth]) if rule.kind == "below" else None


# -- unlocking ----------------------------------------------------------------
class _HeaderStore:
    """crdt_sync's sync ``RemoteStore``, just enough for ``unlock_e2e``.

    ``unlock_e2e`` runs in a worker thread (Argon2id must not block the
    loop); each call hops back to the loop that owns the async client.
    The header is one JSON string leaf, as the Flutter side writes it.
    """

    def __init__(self, raw: Rtdb, loop: asyncio.AbstractEventLoop) -> None:
        self._raw = raw
        self._loop = loop

    def _run[T](self, coro: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def list_directory(self, path: str) -> list[str]:
        """Nothing: only the header is read through here."""
        del path
        return []

    def get_file_text(self, path: str) -> str | None:
        """The header text, or ``None``; a non-string value comes back as JSON."""
        value = self._run(self._raw.get(path))
        if value is None or isinstance(value, str):
            return value
        return _dumps(value)  # not ours: E2eHeaderError, never overwritten

    def put_file_text(self, path: str, text: str, *, message: str) -> None:
        """Write the header as one string leaf."""
        del message
        self._run(self._raw.put(path, text))

    def delete_file(self, path: str, *, message: str = "") -> None:
        """Refused: the header is never deleted."""
        del path, message
        msg = "the tutor never deletes the e2e header"
        raise NotImplementedError(msg)

    def can_access_remote(self) -> bool:
        """Always: a failing call raises on its own."""
        return True


async def unlock(
    rtdb: Rtdb, passphrase: str, params: Argon2Params | None = None
) -> E2eKey:
    """The tutor's key from the shared passphrase (header made on first use).

    Raises:
        E2eLockedError: No passphrase, a wrong one, or an unreadable header.
    """
    if not passphrase:
        msg = "no crdt-sync passphrase on this PC"
        raise E2eLockedError(msg)
    store = _HeaderStore(rtdb.at(""), asyncio.get_running_loop())
    try:
        return await asyncio.to_thread(
            unlock_e2e,
            store,
            path_prefix=LAYOUT.prefix,
            passphrase=passphrase,
            params=params,
            e2e_path=LAYOUT.e2e_path,
        )
    except (E2eWrongPassphraseError, E2eHeaderError) as exc:
        raise E2eLockedError(str(exc) or type(exc).__name__) from exc


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
