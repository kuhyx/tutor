# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Code checks of a lesson turn: its query, and the first probe's wording.

``rejection`` refuses a turn whose query fails, returns nothing or leaks the
result. ``problem`` refuses a first probe after a wrong answer that names a
SQL function or clause (ROUND, CAST, HAVING...) the learner has not typed
themselves, like ``sql_model._problem`` does for hints; after the last re-ask
``generic`` swaps the probe for a nudge. SQL inside a fence is the next query,
not prose.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

from tutor.relay import sql_lesson_prompt as prompt
from tutor.relay.sql_model import tools_named

if TYPE_CHECKING:
    from tutor.relay.sql import Json

WRONG: Final = ("wrong_prediction", "wrong_reasoning", "partial")
NUDGE: Final = "Not quite. Look at the table and the rule above, then try again."
GENERIC_QUESTION: Final = "Which rows does this query return, and why (one sentence)?"
_FENCE: Final = re.compile(r"```.*?```", re.DOTALL)


def _typed(state: dict[str, Any], answer: str) -> set[str]:
    said = " ".join([answer, *(str(e["answer"]) for e in state["history"])])
    return set(re.findall(r"\w+", said.lower()))


def _named(text: str, typed: set[str]) -> list[str]:
    names = tools_named(_FENCE.sub(" ", text))
    return sorted(n for n in names if not set(n.split()) <= typed)


def _first(turn: dict[str, Any], state: dict[str, Any]) -> bool:
    """A wrong answer right after a correct one (or the first answer)."""
    history = state["history"]
    return turn["verdict"] in WRONG and (
        not history or history[-1]["verdict"] not in WRONG
    )


def problem(turn: dict[str, Any], state: dict[str, Any], answer: str) -> str | None:
    """Why ``turn`` is a bad first probe, or ``None``."""
    if not _first(turn, state):
        return None
    typed = _typed(state, answer)
    named = _named(turn["feedback_md"] + "\n" + turn["question_md"], typed)
    if not named:
        return None
    return (
        f"the first probe after a wrong answer named {', '.join(named)}; "
        "it only points at the rule, table or column, naming no function or syntax"
    )


def generic(turn: dict[str, Any], state: dict[str, Any], answer: str) -> dict[str, Any]:
    """``turn`` with the nudge in place of its feedback (and a bare question)."""
    out = {**turn, "feedback_md": NUDGE}
    if _named(turn["question_md"], _typed(state, answer)):
        out["question_md"] = f"```sql\n{turn['query']}\n```\n{GENERIC_QUESTION}"
    return out


def rejection(turn: dict[str, Json], ran: Json, pending: Json) -> str | None:
    """Why the turn's query or text is unusable, or ``None``."""
    if not ran["ok"]:
        return f"your query failed in MySQL ({ran['error']}); write a valid one"
    if not ran["rows"]:
        return "your query returns no rows; use one with a non-empty result"
    if prompt.leaked(turn["question_md"], ran["rows"]):
        return "question_md spells out the query's result; show the query only"
    hidden = pending["rows"] if pending and turn["verdict"] != "correct" else []
    if prompt.leaked(turn["feedback_md"], hidden):
        return "feedback_md reveals the previous result before a correct answer"
    return None
