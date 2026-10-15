# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One structured model call for the curriculum (plans, profiles, cards).

Same isolation as the tutor's session (``session.isolated_options``: no tools,
no MCP, no settings, no hooks, same model); only the output schema differs.
The call is blocking: it runs its own event loop in a worker thread, so it is
safe from a thread *and* from code that already runs inside a loop.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import dataclasses
import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, MODEL_ERROR, RequestError
from tutor.outage import ClaudeUnavailableError
from tutor.session import SessionError, TutorSession, isolated_options

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

_logger = logging.getLogger(__name__)


def options(system: str, schema: dict[str, Any]) -> ClaudeAgentOptions:
    """The tutor's isolated options with ``schema`` as the output format."""
    base = isolated_options(system, structured=False)
    return dataclasses.replace(
        base, output_format={"type": "json_schema", "schema": schema}
    )


STRING: Final = {"type": "string"}


def strict_object(props: dict[str, Any]) -> dict[str, Any]:
    """A JSON-schema object with exactly ``props``, all required."""
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


def array_of(item: dict[str, Any]) -> dict[str, Any]:
    """A JSON-schema array of ``item``."""
    return {"type": "array", "items": item}


def _decode(text: str) -> object:
    """The reply text as JSON (some turns carry it there, not structured)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        msg = "the model returned no structured answer"
        raise RequestError(MODEL_ERROR, msg) from err


async def _ask(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    session = TutorSession(options(system, schema))
    try:
        reply = await session.ask_raw(prompt)
    finally:
        await session.close()
    raw = reply.structured if reply.structured is not None else _decode(reply.text)
    if not isinstance(raw, dict):
        msg = "the model's answer was not an object"
        raise RequestError(MODEL_ERROR, msg)
    return raw


def ask_model(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Blocking structured call; any model failure is ``model_error``.

    An outage is ``claude_unavailable`` instead, its :class:`ClaudeUnavailableError`
    kept as the cause (the relay reads ``reason`` / ``resets_at`` off it).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, _ask(system, prompt, schema))
        try:
            return future.result()
        except ClaudeUnavailableError as err:
            raise RequestError(CLAUDE_UNAVAILABLE, str(err)) from err
        except (SessionError, TimeoutError, OSError) as err:
            _logger.warning("curriculum model call failed: %r", err)
            msg = f"the model call failed: {err}"
            raise RequestError(MODEL_ERROR, msg) from err
