# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The CLI options of a free-model session (``free_backend``, ``claude-free``).

While a free request runs (``backend_mode.FREE``), :func:`applied` points the
session's CLI at the local OmniRoute gateway: its Anthropic-compatible API,
the ``free-best`` chain for every model slot, and the one loopback port the
sandbox forwards (``TUTOR_MODEL_GATEWAY_PORT``, ``tutor_model_sandbox.sh``).
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

from tutor import backend_mode

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

GATEWAY_ENV: Final = "TUTOR_FREE_GATEWAY"  # the sandbox E2E points it at a dead port
DEFAULT_GATEWAY: Final = "http://127.0.0.1:20128"
MODEL: Final = "free-best"


def gateway() -> str:
    """The OmniRoute base URL (``$TUTOR_FREE_GATEWAY`` overrides it)."""
    return os.environ.get(GATEWAY_ENV) or DEFAULT_GATEWAY


def key() -> str:
    """OmniRoute's API key (``~/.config/omniroute/api_key``); "" if missing."""
    path = Path.home() / ".config" / "omniroute" / "api_key"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def applied(options: ClaudeAgentOptions) -> ClaudeAgentOptions:
    """``options`` on the free chain while a free request runs, else unchanged."""
    if not backend_mode.free():
        return options
    url = gateway()
    env = {
        **options.env,
        "ANTHROPIC_BASE_URL": url,
        "ANTHROPIC_AUTH_TOKEN": key(),
        "ANTHROPIC_MODEL": MODEL,
        "ANTHROPIC_SMALL_FAST_MODEL": MODEL,
        "CLAUDE_CODE_SUBAGENT_MODEL": MODEL,
        "TUTOR_MODEL_GATEWAY_PORT": str(urlsplit(url).port or 80),
    }
    return dataclasses.replace(options, model=MODEL, env=env)
