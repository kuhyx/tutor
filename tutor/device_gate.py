# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Let one paired phone reach the tutor page over the public hostname.

Caddy (``tutor.kuhy.duckdns.org``) forwards to the loopback server, so every
request arrives from 127.0.0.1 and ``X-Forwarded-*`` is whatever the sender
wrote. The one trustworthy signal is the ``Host`` header (the PC's page sends a
loopback origin; Caddy passes the visitor's name through), so that alone says
"public". A public request needs the per-device cookie, and even a paired
phone reaches only the page (``/``, ``/app/*``): never ``/api/*``, which runs
Claude. The same shape as the todoImplementer board's gate
(``todoImplementer/DOCS-phone.md``). Record: ``DOCS-public.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
import time
from typing import TYPE_CHECKING, Final
from urllib.parse import parse_qs

from starlette.datastructures import Headers

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.types import Scope

_logger = logging.getLogger(__name__)
COOKIE: Final = "tutor_device"
PAIRED_KEY: Final = "tutor.paired"
DEFAULT_HOST: Final = "tutor.kuhy.duckdns.org"
MAX_AGE: Final = 34_560_000  # 400 days, the longest Chrome keeps a cookie
CODE_TTL: Final = 300.0
MAX_PENDING: Final = 5
MAX_TOKEN: Final = 128
_PAGE_PATHS: Final = frozenset({"/", "/app"})
_PAGE_METHODS: Final = frozenset({"GET", "HEAD"})
NO_STORE: Final = {"Cache-Control": "no-store"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class DeviceStore:
    """The paired phones: a private JSON list of token hashes (never a token)."""

    def __init__(self, path: Path) -> None:
        """Keep the list at ``path``; a missing or malformed file pairs nobody."""
        self.path = path

    def _rows(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []  # nobody has paired yet
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            _logger.warning(
                "device list %s unreadable: nobody paired", self.path, exc_info=True
            )
            return []
        if not isinstance(data, list):
            _logger.warning("device list %s is not a list: nobody paired", self.path)
            return []
        return [row for row in data if isinstance(row, dict)]

    def check(self, token: str) -> bool:
        """Whether ``token`` belongs to a paired phone (every row is compared)."""
        want = _sha(token)
        found = False
        for row in self._rows():
            have = row.get("sha256")
            if isinstance(have, str) and hmac.compare_digest(have, want):
                found = True
        return found

    def add(self, token: str, user_agent: str | None) -> None:
        """Pair a phone: store the token's hash and the first 80 chars of its UA."""
        row = {
            "sha256": _sha(token),
            "created": int(time.time()),
            "ua": (user_agent or "")[:80],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump([*self._rows(), row], out)
        tmp.replace(self.path)


class PairCodes:
    """Single-use pairing codes, five minutes long, kept in server memory."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        """Mint and redeem against ``clock`` (injected by tests)."""
        self._clock = clock
        self._pending: dict[str, float] = {}

    def mint(self) -> str:
        """A new code; the oldest pending one is dropped past five."""
        now = self._clock()
        self._pending = {h: t for h, t in self._pending.items() if t > now}
        while len(self._pending) >= MAX_PENDING:
            del self._pending[next(iter(self._pending))]
        code = secrets.token_urlsafe(16)
        self._pending[_sha(code)] = now + CODE_TTL
        return code

    def redeem(self, code: str) -> bool:
        """Spend ``code``: true once, only while it has not expired."""
        expires = self._pending.pop(_sha(code), 0.0)
        return expires > self._clock()


def device_tokens(cookie_headers: list[str]) -> list[str]:
    """Every ``tutor_device`` value in the Cookie headers."""
    found = []
    for line in cookie_headers:
        for part in line.split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE and 0 < len(value) <= MAX_TOKEN:
                found.append(value)
    return found


@dataclass(frozen=True)
class PublicGate:
    """Decides what a request on the public hostname may do."""

    store: DeviceStore
    codes: PairCodes
    host: str

    @classmethod
    def from_env(cls) -> PublicGate | None:
        """The live gate: ``$TUTOR_PUBLIC_HOST`` (empty: off), ``$TUTOR_DEVICES``."""
        host = os.environ.get("TUTOR_PUBLIC_HOST", DEFAULT_HOST).strip().lower()
        if not host:
            return None
        raw = os.environ.get("TUTOR_DEVICES", "")
        path = Path(raw) if raw else Path.home() / ".config" / "tutor" / "devices.json"
        return cls(DeviceStore(path), PairCodes(), host)

    def is_public(self, host: str) -> bool:
        """Whether ``host`` is exactly the public name (no port, any case)."""
        return host == self.host

    def refusal(self, scope: Scope) -> tuple[int, str] | None:
        """The (status, body) to refuse a public request with; None lets it through."""
        method = scope.get("method", "GET")
        path = scope["path"]
        if scope["type"] == "http" and method == "GET" and path == "/pair":
            return None  # the code in the query is the credential
        headers = Headers(scope=scope)
        tokens = device_tokens(headers.getlist("cookie"))
        if not any(self.store.check(token) for token in tokens):
            return 401, ""
        if method not in _PAGE_METHODS or not (
            path in _PAGE_PATHS or path.startswith("/app/")
        ):
            return 403, ""
        scope[PAIRED_KEY] = True
        return None

    def mint_url(self) -> str:
        """A pairing link for the phone (``scripts/tutor_pair.sh`` shows it)."""
        return f"https://{self.host}/pair?c={self.codes.mint()}"

    def redeem(self, query: str, user_agent: str | None) -> str | None:
        """Spend the code in ``query``; the new device's cookie line, or None."""
        codes = parse_qs(query).get("c", [])
        if len(codes) != 1 or not self.codes.redeem(codes[0]):
            return None
        token = secrets.token_urlsafe(32)
        self.store.add(token, user_agent)
        attrs = f"Max-Age={MAX_AGE}; Path=/; Secure; HttpOnly; SameSite=Lax"
        return f"{COOKIE}={token}; {attrs}"
