# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""One checked coach reply: ask, check every gate, re-ask up to 3 times."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import focus_hook
from tutor.curriculum.modelcall import ask_model
from tutor.relay import lc_backend, lc_checks, lc_prompt
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from tutor.relay.lc_state import State

_logger = logging.getLogger(__name__)
TRIES: Final = 3
MAX_BELIEF: Final = 200
HINTS: Final = {"hint": 1, "hint!": 2}
# A one-word "ok" must not back ~20 min of focus time; this many stripped chars
# of kuhy's own text (or a deliberate word below) is a turn worth counting.
MIN_BEAT_CHARS: Final = 20
_BEAT_WORDS: Final = frozenset({"reveal", "write it", *HINTS})


def heartbeat() -> None:
    """Count one coach turn or run as focus work; never fails the request."""
    try:
        fp = focus_hook.load_fp()
        if fp is not None:
            fp.record_activity("tutor", "heartbeat")
    except focus_hook.BROKEN:
        _logger.exception("coach heartbeat skipped")


def turn_counts(text: str, intent: str, out: dict[str, Any]) -> bool:
    """Whether this ``lc_turn`` backs the focus timer (a held one never does)."""
    if out.get("held"):
        return False
    said = text.strip()
    deliberate = intent == "solved" or said.lower() in _BEAT_WORDS
    return deliberate or len(said) >= MIN_BEAT_CHARS


def log(state: State, event: str, **fields: object) -> None:
    """Append to the coach's session log; a log failure never fails a request."""
    try:
        lc_backend.coach().log(state["slug"], event, **fields)
    except OSError, ValueError, LookupError:
        _logger.exception("coach session log skipped (%s)", event)


@dataclass(frozen=True)
class Rules:
    """How strictly to check a reply: rung ``ceiling``, kuhy's words, ``relaxed``."""

    ceiling: int
    said: str = ""
    note: str = ""
    relaxed: bool = False


def _problem(state: State, reply: str, rung: str, rules: Rules) -> str:
    """What is wrong with this reply ("" when nothing)."""
    if not reply:
        return "it was empty."
    kuhy = [e["md"] for e in state["thread"] if e["mine"]] + [rules.said]
    names = lc_checks.identifiers(
        state["starter"].get(state["lang"], ""), state["statement_md"], state["kind"]
    )
    checks: list[str | None] = []
    if not rules.relaxed:
        checks.append(lc_checks.question_problem(reply))
        checks.append(lc_checks.rung_problem(rung, rules.ceiling))
        checks.append(
            lc_checks.code_problem(
                reply, names, "\n".join([*kuhy, state["statement_md"]]), state["kind"]
            )
        )
        if not state["code_seen"] and (named := lc_backend.coach().leaked(reply, kuhy)):
            checks.append(f"it names {', '.join(named)} before kuhy's first code.")
    return next((c for c in checks if c), "")


async def ask_reply(state: State, message: str, rules: Rules) -> dict[str, Any]:
    """The checked reply ``{"reply_md", "rung", "belief"}``; ``model_error`` after 3."""
    system = lc_prompt.system(lc_backend.coach().system_prompt(state["statement_md"]))
    retry = ""
    for _ in range(TRIES):
        prompt = lc_prompt.turn(state, message, note=rules.note, retry=retry)
        raw = await asyncio.to_thread(ask_model, system, prompt, lc_prompt.TURN_SCHEMA)
        reply, rung = str(raw.get("reply_md", "")).strip(), str(raw.get("rung", ""))
        retry = _problem(state, reply, rung.strip(), rules)
        if not retry:
            belief = str(raw.get("belief", "")).strip()[:MAX_BELIEF]
            return {"reply_md": reply, "rung": rung.strip(), "belief": belief}
        _logger.warning("coach reply rejected: %s", retry)
    msg = "the coach gave no valid reply; try again"
    raise RequestError(msg, code="model_error", retry=True)
