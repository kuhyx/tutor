# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What the problem coach tells the model, and the schemas it must answer in."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum.modelcall import STRING, array_of, strict_object

if TYPE_CHECKING:
    from tutor.relay.lc_state import State

BOOL: Final = {"type": "boolean"}
TURN_SCHEMA: Final = strict_object(
    {"reply_md": STRING, "rung": STRING, "belief": STRING}
)
GRADE_SCHEMA: Final = strict_object(
    {"mechanism_ok": BOOL, "missing": STRING, "retired": BOOL}
)
CARDS_SCHEMA: Final = strict_object(
    {
        "entries": array_of(STRING),
        "proposals": array_of(
            strict_object(
                {
                    "name": STRING,
                    "aliases": array_of(STRING),
                    "properties": array_of(STRING),
                }
            )
        ),
    }
)
HARD_RULES: Final = """

# Reply format (the relay checks every point and re-asks on a violation)
Answer with JSON: reply_md (markdown for kuhy), rung, belief.
- ONE question or ONE instruction per reply, at the end. Never two question marks.
- rung: "H0".."H3" when the reply is a hint at that rung, else "". One rung per
  reply, the smallest that helps; climb only on a hint request or a failed run.
- Never name an operation, structure or algorithm before kuhy's first code
  unless kuhy named it first. Never write code kuhy could paste, and never
  use the problem's own names in code; toy snippets use unrelated data.
- belief: the wrong belief kuhy opened with, in kuhy's words, when kuhy stated
  one and you have not recorded it; else "".
- No emoji. Never answer your own question."""
OPENER: Final = (
    "Session start. Restate the problem in at most 3 sentences, then ask ONE "
    "calibration question: is the problem or the tool unclear? Do not hint."
)
REVEAL: Final = (
    "kuhy typed reveal. Walk the solution line by line, tied to the hint rungs "
    "seen so far. End with one instruction for kuhy."
)
BUDGET_NOTE: Final = (
    "[app: budget reached] Reply with a summary of at most 2 lines and ask for "
    "a full attempt."
)
EXIT_ASK: Final = (
    "kuhy says the problem is solved and explains it. Judge ONLY whether the "
    "explanation states the key mechanism. mechanism_ok true/false, missing: "
    "the missing step in a few words (empty when ok), retired: whether kuhy "
    "corrected the opening belief (false when there is none)."
)
BELIEF_ASK: Final = (
    "Quote this belief kuhy opened with and ask what is wrong with it now. "
    "End with that one question."
)


def system(coach_prompt: str) -> str:
    """The coach library's prompt plus the relay's format rules."""
    return coach_prompt + HARD_RULES


def _context(state: State) -> dict[str, Any]:
    return {
        "kind": state["kind"],
        "language": state["lang"],
        "rung_so_far": state["rung"],
        "turns_used": state["turns"],
        "code_seen": state["code_seen"],
        "last_run_failed": state["failed"],
        "revealed": state["revealed"],
    }


def turn(state: State, message: str, *, note: str = "", retry: str = "") -> str:
    """The prompt of one coach turn: context, the chat tail, kuhy's message."""
    tail = "\n".join(
        f"{'kuhy' if e['mine'] else 'coach'}: {e['md']}" for e in state["thread"][-16:]
    )
    parts = [f"State: {json.dumps(_context(state))}", f"Conversation:\n{tail}"]
    if state["belief"]:
        parts.append(f"Recorded opening belief: {state['belief']}")
    parts.append(f"{note}\nkuhy: {message}".strip())
    if retry:
        parts.append(f"Your previous reply was rejected: {retry} Fix it.")
    return "\n\n".join(parts)
