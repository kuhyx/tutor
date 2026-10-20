# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The sandboxed tutor CLI's login: a copy of the Claude access token only.

kuhy's ``~/.claude/.credentials.json`` stays outside the sandbox
(``tutor.research``): it also holds the refresh token and every MCP server's
OAuth tokens. :class:`Login` copies only ``claudeAiOauth`` minus
``refreshToken`` into the scratch HOME before every turn. Without a refresh
token the CLI inside never refreshes (a refresh rotates the token, which
would log kuhy's own CLI out; the SDK strips it for the same reason when it
copies a login). When the token is within the CLI's refresh margin, the
host's own CLI (no tools, no settings) refreshes it in place first.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING, Final

import claude_agent_sdk

from tutor.session import MODEL

if TYPE_CHECKING:
    from collections.abc import Callable

# The CLI refreshes its token within 5 minutes of expiry (``NT`` in the CLI).
REFRESH_MARGIN_MS: Final = 300_000
_logger = logging.getLogger(__name__)


def real_cli() -> Path:
    """The claude binary to run: ``$TUTOR_MODEL_CLI``, else the SDK's bundled one."""
    if override := os.environ.get("TUTOR_MODEL_CLI"):
        return Path(override)
    bundled = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    if bundled.is_file():
        return bundled
    found = shutil.which("claude")
    return Path(found) if found else bundled


def host_login_file() -> Path:
    """Kuhy's own CLI login (resolved at call time)."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"
    return Path(base) / ".credentials.json"


def sync_login(box_home: Path) -> int | None:
    """Copy the host's Claude access token into ``box_home``; its expiry (ms).

    Only ``claudeAiOauth`` minus ``refreshToken`` is written (0600, atomic).
    No readable host login: nothing is written and None is returned.
    """
    try:
        raw = json.loads(host_login_file().read_text(encoding="utf-8"))
        oauth = dict(raw["claudeAiOauth"])
    except (OSError, ValueError, KeyError, TypeError) as err:
        _logger.warning("no host Claude login to copy: %r", err)
        return None
    oauth.pop("refreshToken", None)
    target = box_home / ".claude" / ".credentials.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".credentials.")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump({"claudeAiOauth": oauth}, out)
    Path(tmp).replace(target)
    expires = oauth.get("expiresAt")
    return int(expires) if isinstance(expires, (int, float)) else None


def refresh_host_login(cwd: Path) -> None:
    """Let the host's CLI refresh kuhy's login: one tiny call, nothing loaded."""
    cmd = [
        str(real_cli()),
        "-p",
        "Reply with OK.",
        "--tools=",
        "--setting-sources=",
        "--strict-mcp-config",
        "--max-turns=1",
        "--no-session-persistence",
        f"--model={MODEL}",
    ]
    cwd.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True, timeout=60)


class Login:
    """The scratch HOME's login copy, kept fresh before every turn."""

    def __init__(
        self,
        box_home: Path,
        *,
        refresh: Callable[[], None] | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        """Copy into ``box_home``; ``refresh`` renews the host login."""
        self._home = box_home
        self._refresh = refresh or (lambda: refresh_host_login(box_home.parent))
        self._now = now

    def ensure(self) -> None:
        """Copy the login; one about to expire is refreshed on the host first.

        Never raises: a failure is logged and the turn reports the CLI's error.
        """
        try:
            expires = sync_login(self._home)
            if expires is None or expires - self._now() * 1000 > REFRESH_MARGIN_MS:
                return
            self._refresh()
            sync_login(self._home)
        except (OSError, subprocess.SubprocessError) as err:
            _logger.warning("could not refresh the Claude login: %r", err)
