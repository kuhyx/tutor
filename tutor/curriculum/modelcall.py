# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One structured model call for the curriculum (plans, profiles, cards).

Same isolation as the tutor's session (``session.isolated_options``: no tools,
no MCP, no settings, no hooks); only the output schema differs. The model
and effort are a tier's (``tutor.tiers``): :func:`ask_draft` writes cards,
:func:`ask_repeat` serves what the learner repeats; no tier is Sonnet at
medium, as before. Every tiered call logs its model, effort and duration.
The call is blocking: it runs its own event loop in a worker thread, so it is
safe from a thread *and* from code that already runs inside a loop.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import dataclasses
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Final

from tutor import local_model, outage
from tutor.curriculum.errors import CLAUDE_UNAVAILABLE, MODEL_ERROR, RequestError
from tutor.outage import ClaudeUnavailableError
from tutor.session import TURN_TIMEOUT, SessionError, TutorSession, isolated_options
from tutor.tiers import DRAFT, REPEAT

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeAgentOptions

    from tutor.tiers import Tier

_logger = logging.getLogger(__name__)


def options(
    system: str, schema: dict[str, Any], tier: Tier | None = None
) -> ClaudeAgentOptions:
    """The tutor's isolated options with ``schema`` as the output format."""
    base = isolated_options(system, structured=False)
    if tier is not None:
        base = dataclasses.replace(base, model=tier.model, effort=tier.effort)
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


async def _ask(
    system: str, prompt: str, schema: dict[str, Any], tier: Tier | None
) -> dict[str, Any]:
    made = options(system, schema, tier)
    session = TutorSession(made, tier.timeout if tier else TURN_TIMEOUT)
    try:
        reply = await session.ask_raw(prompt)
    finally:
        await session.close()
    raw = reply.structured if reply.structured is not None else _decode(reply.text)
    if not isinstance(raw, dict):
        msg = "the model's answer was not an object"
        raise RequestError(MODEL_ERROR, msg)
    return raw


def ask_model(
    system: str, prompt: str, schema: dict[str, Any], tier: Tier | None = None
) -> dict[str, Any]:
    """Blocking structured call; any model failure is ``model_error``.

    An outage is ``claude_unavailable`` instead, its :class:`ClaudeUnavailableError`
    kept as the cause (the relay reads ``reason`` / ``resets_at`` off it).
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, _ask(system, prompt, schema, tier))
        try:
            return future.result()
        except ClaudeUnavailableError as err:
            raise RequestError(CLAUDE_UNAVAILABLE, str(err)) from err
        except (SessionError, TimeoutError, OSError) as err:
            _logger.warning("curriculum model call failed: %r", err)
            msg = f"the model call failed: {err}"
            raise RequestError(MODEL_ERROR, msg) from err


def _tiered(
    tier: Tier, system: str, prompt: str, schema: dict[str, Any]
) -> dict[str, Any]:
    """One call on ``tier``, its model, effort and duration logged."""
    began = time.monotonic()
    try:
        return ask_model(system, prompt, schema, tier)
    finally:
        _logger.warning(
            "curriculum model call (%s tier): %s at %s, %.0f s",
            tier.name,
            tier.model,
            tier.effort,
            time.monotonic() - began,
        )


def ask_draft(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """:func:`ask_model` on the draft tier (Fable 5.2, ``xhigh``)."""
    return _tiered(DRAFT, system, prompt, schema)


def ask_repeat(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """:func:`ask_model` on the repeat tier (Sonnet, ``high``)."""
    return _tiered(REPEAT, system, prompt, schema)


def ask_or_local(
    system: str, prompt: str, schema: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """:func:`ask_model`, or the local model while Claude is unavailable.

    Returns the answer and the local model's name when it gave the answer
    (``None``: Claude did). Only for answers that code checks or kuhy confirms
    before anything is kept: coach turns, the exit grade, toolbox matches, SQL
    hints. Card writers never call it, so a weak local answer never lands in a
    subject. While a recorded outage window is open no CLI is spawned. When
    the local model is down too, the Claude error is raised as before.
    """
    failure: Exception
    try:
        outage.ensure_available(time.time())
        return ask_model(system, prompt, schema), None
    except ClaudeUnavailableError as err:
        _logger.warning("Claude outage window open (%s); asking the local model", err)
        failure = err
    except RequestError as err:
        if err.code != CLAUDE_UNAVAILABLE:
            raise
        _logger.warning("Claude unavailable (%s); asking the local model", err)
        failure = err
    local = local_model.ask(system, prompt, schema)
    if local is None:
        raise failure
    return local, local_model.MODEL
