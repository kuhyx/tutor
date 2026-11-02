# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What the lesson model is told, what it must return, and its checks."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Final

from tutor.relay.sql_lesson_plan import PLAN

if TYPE_CHECKING:
    from tutor.relay.sql import Json

VERDICTS: Final = ("start", "correct", "wrong_prediction", "wrong_reasoning", "partial")
_BACKREF: Final = re.compile(
    r"\b(rewrite|earlier|previous(ly)?|above|before|same query|that query|"
    r"last query|q\d+|query \d+|question \d+)\b",
    re.IGNORECASE,
)
MIN_CHECKS: Final = 2
MULTI_CELL: Final = 2
PROMPT_ROWS: Final = 12
SCHEMA: Final = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "feedback_md": {"type": "string"},
        "mastered": {"type": "boolean"},
        "summary_md": {"type": "string"},
        "question_md": {"type": "string"},
        "query": {"type": "string"},
    },
    "required": [
        "verdict",
        "feedback_md",
        "mastered",
        "summary_md",
        "question_md",
        "query",
    ],
    "additionalProperties": False,
}
SYSTEM: Final = """\
You are a Socratic MySQL 8 tutor guiding one learner through ONE concept at a \
time. The learner's tables are always shown to them; the REAL output of every \
query is computed by the database and given to you as ground truth. Never \
invent result rows.

Each turn you ask ONE question: "which rows does this query return, and why \
(one sentence)?" with a single SELECT in `query` (it runs on the shown \
tables) that you also show in question_md in a ```sql fence. Do not put the \
result in question_md.

Grade the PREDICTION and the REASONING against the real output and the \
concept goal. verdict: start (no answer yet), correct (prediction and reason \
both right), wrong_prediction, wrong_reasoning (right list, wrong or missing \
reason), partial. On anything but correct: do NOT give the answer, the rule \
or the result. Probe instead: a variant query that contradicts their model \
(e.g. the NOT(...) of it), a plain-language reframe ("if you do not know X, \
do you know not-X?"), or "fill the unknown both ways". Then ask the next \
question (a new query that tests their repaired model). Confirm a rule only \
once the learner has stated it in their own words; set mastered=true only \
then (and verdict correct), with summary_md = a compact markdown summary \
table of the concept. Otherwise summary_md is "".

The learner must never scroll back: a question that mentions an earlier \
query, answer or question ("rewrite Q6 so it works", "the earlier query") \
restates that query's SQL in full in a ```sql fence inside the same \
question_md, and quotes the learner's earlier answer if it relies on it. \
Never refer to an earlier turn by number alone.

Mini-check phase: short fresh variant queries, one per turn; judge them the \
same way. Be brief, warm, concrete; no company names; feedback_md is 1-4 \
sentences ("" on the opening turn). query must be one SELECT, no semicolon \
chains, with a fully determined row order.\
"""


def _table_text(tables: dict[str, Any]) -> str:
    out = []
    for name, table in tables.items():
        rows = "\n".join(" | ".join(r) for r in table["rows"][:PROMPT_ROWS])
        out.append(f"{name}({', '.join(table['columns'])}):\n{rows}")
    return "\n\n".join(out)


def _past(entry: dict[str, Any]) -> str:
    return (
        f"- query: {entry['query']}\n  real output: {json.dumps(entry['rows'])}\n"
        f"  learner said: {entry['answer']}\n  verdict: {entry['verdict']}"
    )


def build(
    state: dict[str, Any], tables: dict[str, Any], answer: str | None, note: str
) -> str:
    """The user prompt for one turn (``answer`` None = the opening question)."""
    concept = PLAN[state["topic"]][state["index"]]
    parts = [
        (
            f"Concept: {concept.title}\n"
            f"Goal (never state it before the learner does): {concept.goal}"
        ),
        f"Phase: {state['phase']}"
        + (
            f" (right answers still needed: {state['checks_left']})"
            if state["phase"] == "check"
            else ""
        ),
        f"Tables the learner sees:\n{_table_text(tables)}",
    ]
    if state["history"]:
        parts.append(
            "Recent turns:\n" + "\n".join(_past(e) for e in state["history"][-6:])
        )
    pending = state["pending"]
    if answer is None or pending is None:
        parts.append("Opening question: there is no learner answer yet.")
    else:
        parts.append(
            f"Pending question:\n{pending['question_md']}\nReal output of its "
            f"query (hidden from the learner): {json.dumps(pending['rows'])}\n"
            f"Learner's answer:\n{answer}"
        )
    return "\n\n".join(parts) + note


def leaked(text: str, rows: list[list[str]]) -> bool:
    """Whether ``text`` spells out a multi-cell result row (the answer)."""
    for row in rows:
        if len(row) >= MULTI_CELL:
            for sep in (" | ", "|", "\t", ", ", ","):
                if sep.join(row) in text:
                    return True
    return False


def problem(raw: dict[str, Any], *, answered: bool) -> str | None:
    """What is wrong with the model's turn, or ``None``."""
    text = {
        k: raw.get(k) for k in ("feedback_md", "summary_md", "question_md", "query")
    }
    if raw.get("verdict") not in VERDICTS:
        return "verdict is not one of " + ", ".join(VERDICTS)
    if not all(isinstance(v, str) for v in text.values()):
        return "feedback_md, summary_md, question_md and query must be strings"
    for key in ("question_md", "query"):
        if not str(text[key]).strip():
            return f"{key} is empty"
    if answered and raw.get("mastered") is True and not str(text["summary_md"]).strip():
        return "mastered=true needs a summary_md table"
    return None


def _squash(sql: str) -> str:
    return " ".join(sql.lower().split())


def missing_backref(question_md: str, earlier: list[str]) -> str | None:
    """Why a question that points back lacks the earlier SQL, or ``None``."""
    if not earlier or not _BACKREF.search(question_md):
        return None
    shown = _squash(question_md)
    if any(_squash(q) in shown for q in earlier):
        return None
    return (
        "question_md points at an earlier query but does not restate its SQL; "
        "restate it in full inline (the learner must never scroll)"
    )


def clean(raw: dict[str, Json]) -> dict[str, Json]:
    """The turn's fields, stripped, in their final types."""
    return {
        "verdict": raw["verdict"],
        "mastered": raw.get("mastered") is True,
        **{
            k: raw[k].strip()
            for k in ("feedback_md", "summary_md", "question_md", "query")
        },
    }
