# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Ids: subject / module / card slugs, ULID event ids and the device id.

Slugs are words of ``[a-z0-9ąćęłńóśźż]`` joined by single hyphens, at most 48
characters (``DOCS-contract.md`` §3); nothing builds a path from an id that
did not pass :func:`valid_id`. The whitelist holds only precomposed letters, so
an NFD spelling ("o" + U+0301) is rejected and one word is one id.
"""

from __future__ import annotations

import re
import secrets
import threading
from typing import TYPE_CHECKING, Final
import unicodedata
import uuid

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

MAX_ID: Final = 48
SLUG_CHARS: Final = "a-z0-9ąćęłńóśźż"
_ID: Final = re.compile(rf"[{SLUG_CHARS}]+(?:-[{SLUG_CHARS}]+)*")
_NON_SLUG: Final = re.compile(rf"[^{SLUG_CHARS}]+")
_WORD: Final = re.compile(rf"[{SLUG_CHARS}]+")
_CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
_MAX_RAND: Final = (1 << 80) - 1
_MONO: list[int] = [0, 0]  # last (ms, random part) handed out
_MONO_LOCK: Final = threading.Lock()


def valid_id(value: object) -> bool:
    """Whether ``value`` is a usable subject / module / card id."""
    return (
        isinstance(value, str)
        and len(value) <= MAX_ID
        and _ID.fullmatch(value) is not None
    )


def tokenize(text: str) -> list[str]:
    """Lowercase words of ``text``: runs of the slug characters, NFC first.

    The one word tokenizer for matching and search, so a Polish word such as
    "pojęcia" stays whole instead of splitting at "ę", whichever way the
    letter was composed.
    """
    return _WORD.findall(unicodedata.normalize("NFC", text.lower()))


def valid_eid(value: object) -> bool:
    """Whether ``value`` is a ULID (26 Crockford base32 characters)."""
    return isinstance(value, str) and _ULID.fullmatch(value) is not None


def slug(text: str, taken: Collection[str] = (), fallback: str = "item") -> str:
    """A fresh id from free text: lowercase words, cut at a word, unique.

    A clash with ``taken`` gets ``-2``, ``-3``... appended (still <= 48 ch).
    Polish letters are kept; the text is composed to NFC after casefolding so
    "o" + U+0301 and "ó" give the same id.
    """
    folded = unicodedata.normalize("NFC", text.casefold())
    words = [w for w in _NON_SLUG.split(folded) if w]
    base = ""
    for word in words:
        longer = f"{base}-{word}" if base else word
        if len(longer) > MAX_ID - 3:
            break
        base = longer
    base = base or (words[0][: MAX_ID - 3] if words else fallback)
    candidate, n = base, 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, digit = divmod(value, 32)
        chars.append(_CROCKFORD[digit])
    return "".join(reversed(chars))


def ulid(at_ms: int, entropy: bytes | None = None) -> str:
    """A ULID: 48-bit ms timestamp then 80 random bits (or ``entropy``).

    Without ``entropy`` the ids are monotonic within this process: a second
    id in the same ms is the previous one + 1, so two events the worker
    writes in one ms (taught, then untaught) fold in the order written.
    """
    if entropy is not None:
        rand = int.from_bytes(entropy[:10].ljust(10, b"\0"), "big")
        return _base32(at_ms, 10) + _base32(rand, 16)
    with _MONO_LOCK:
        last_ms, last_rand = _MONO
        if at_ms <= last_ms and last_rand < _MAX_RAND:
            at_ms, rand = last_ms, last_rand + 1
        else:
            rand = int.from_bytes(secrets.token_bytes(10), "big") >> 1
        _MONO[:] = [at_ms, rand]
    return _base32(at_ms, 10) + _base32(rand, 16)


def device_id(path: Path) -> str:
    """This install's device id: the uuid4 in ``path``, written once.

    Same file format as crdt_sync's ``load_device_identity`` (one uuid, one
    line), so the relay worker and the engine share one id.
    """
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    minted = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{minted}\n", encoding="utf-8")
    return minted
