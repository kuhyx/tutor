# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The local model (Ollama) for replies Claude cannot give while its limit is spent.

Same model and endpoint as ``leetcode_coach.local_backend``: one non-streaming
``/api/chat`` call, the JSON schema passed as ``format`` so the reply has the
shape Claude's structured output would have. ``None`` means "not here
either": the caller keeps its ``claude_unavailable``.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Final

import httpx

__all__ = ["ask", "chat", "httpx", "ready"]

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)

URL: Final = "http://localhost:11434/api/chat"
TAGS_URL: Final = "http://localhost:11434/api/tags"
PROBE_S: Final = 2.0
MODEL: Final = "qwen3:30b-a3b-instruct-2507-q4_K_M"
TIMEOUT_S: Final = 180.0  # the first call also loads the model into VRAM
# Ollama's default context (8192) silently truncates a tutor system prompt
# plus a session's history; 16k still fits the 3090 beside the weights.
NUM_CTX: Final = 16384
KEEP_ALIVE: Final = "15m"  # an outage lasts hours: do not reload every turn

type Post = Callable[[dict[str, Any]], dict[str, Any]]


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    """One POST to Ollama; its JSON body."""
    response = httpx.post(URL, json=payload, timeout=TIMEOUT_S)
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body


def ready() -> bool:
    """Whether Ollama answers and has :data:`MODEL` (a quick probe, no load)."""
    try:
        response = httpx.get(TAGS_URL, timeout=PROBE_S)
        response.raise_for_status()
        names = [m.get("name") for m in response.json().get("models", [])]
    except (httpx.HTTPError, OSError, ValueError, AttributeError) as err:
        _logger.warning("local model unreachable: %r", err)
        return False
    return MODEL in names


def chat(
    system: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    post: Post = _post,
) -> dict[str, Any] | None:
    """The local model's structured answer to a conversation, or ``None``."""
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": schema,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX},
        "messages": [{"role": "system", "content": system}, *messages],
    }
    try:
        content = str(post(payload).get("message", {}).get("content") or "")
        raw = json.loads(content)
    except (httpx.HTTPError, OSError, ValueError) as err:
        _logger.warning("local model did not answer: %r", err)
        return None
    return raw if isinstance(raw, dict) else None


def ask(
    system: str, prompt: str, schema: dict[str, Any], post: Post = _post
) -> dict[str, Any] | None:
    """One question to the local model; its structured answer or ``None``."""
    return chat(system, [{"role": "user", "content": prompt}], schema, post)
