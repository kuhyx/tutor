# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Model-backed SQL kinds: Socratic hints and generated drills."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING, Any, Final

from tutor import outage
from tutor.curriculum.modelcall import STRING, ask_model, strict_object
from tutor.relay.errors import RequestError
from tutor.relay.sql import Json, engine_call, wire

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

_logger = logging.getLogger(__name__)
RETRIES: Final = 2
MAX_QUESTION: Final = 400
SPEC_FIELDS: Final = ("title", "topic", "task_md", "schema_sql", "reference_sql")
HINT_SCHEMA: Final = strict_object({"question": STRING})
SPEC_SCHEMA: Final = strict_object(dict.fromkeys(SPEC_FIELDS, STRING))
_STATEMENT: Final = re.compile(
    r"\bselect\b.*?\bfrom\b|\b(?:insert\s+into|delete\s+from|drop\s+table"
    r"|update\s+\w+\s+set)\b",
    re.IGNORECASE | re.DOTALL,
)
# Names that give the tool away: SQL-only words match in any case, common
# English ones (FORMAT, CASE, COUNT...) only when written as SQL, and any call.
_TOOL_LOWER: Final = re.compile(
    r"\b(?:round|cast|convert|ifnull|coalesce|nullif|date_format|str_to_date|"
    r"date_add|date_sub|datediff|row_number|dense_rank|substring|truncate)\b",
    re.IGNORECASE,
)
_CALL: Final = re.compile(r"\b(\w+)\(")
_TOOL_UPPER: Final = re.compile(
    r"\b(?:FORMAT|CASE|COUNT|SUM|AVG|MIN|MAX|CONCAT|RANK|FLOOR|CEIL|DECIMAL|"
    r"GROUP BY|ORDER BY|HAVING|JOIN|LIKE|EXTRACT|OVER)\b"
)
HINT_SYSTEM: Final = (
    "You coach a student practising MySQL 8 for a timed test. Reply with ONE "
    "short Socratic question that nudges them toward the next step. Never give "
    "the answer, never write a SQL statement or a code block, never name the "
    "full solution. One question mark, at the end. Hints graduate from the "
    "smallest nudge upward: level 1 only points at the relevant rule, table "
    "or column and names NO function or syntax; level 2 names the concept "
    "area; from level 3 you may name a function, still as a question."
)
LEVEL_NOTES: Final = (
    "point at the rule, table or column only; name no function or syntax",
    "name the concept area, still no function name",
    "you may now name the function or clause, as a question",
)
GENERATE_SYSTEM: Final = (
    "You write one SQL practice drill for MySQL 8.0.33. schema_sql: CREATE "
    "TABLE and INSERT statements only (2-3 small tables, 5-12 rows each, with "
    "some NULLs and ties). reference_sql: ONE SELECT whose output order is "
    "fully determined (ORDER BY every tie). task_md: markdown naming the "
    "expected columns, their order and the row order. Use generic business "
    "wording; never a real company or product name."
)


def tools_named(text: str) -> set[str]:
    """Lower-cased function/clause names ``text`` gives away (see the patterns)."""
    found = {m.group(0) for m in _TOOL_LOWER.finditer(text)}
    found |= {m.group(0) for m in _TOOL_UPPER.finditer(text)}
    found |= {m.group(1) for m in _CALL.finditer(text)}
    return {name.lower() for name in found}


def _problem(question: str, level: int) -> str | None:
    if not question:
        return "it was empty"
    if len(question) > MAX_QUESTION:
        return f"it was longer than {MAX_QUESTION} characters"
    if "```" in question or _STATEMENT.search(question):
        return "it contained SQL code"
    if question.count("?") != 1 or not question.endswith("?"):
        return "it was not exactly one question ending in a question mark"
    if level <= len(LEVEL_NOTES) - 1 and tools_named(question):
        return "it named a function or syntax; a first hint only points at the rule"
    return None


def _level(body: dict[str, Any]) -> int:
    """1 for the first hint of a drill, one more per hint already shown."""
    return len(body["history"]) + 1


def _hint_prompt(drill: dict[str, Json], body: dict[str, Any]) -> str:
    parts = [f"Task:\n{drill['task_md']}", f"Schema:\n{drill['schema_sql']}"]
    if drill.get("query"):
        parts.append(f"The student must predict the output of:\n{drill['query']}")
    parts.append(
        f"Student's SQL so far:\n{body['sql']}"
        if body["sql"].strip()
        else "The student has not written any SQL yet."
    )
    if body["last_result"] is not None:
        parts.append(f"Last run:\n{json.dumps(body['last_result'])}")
    if body["history"]:
        asked = "\n".join(f"- {q}" for q in body["history"])
        parts.append(f"Questions already asked (do not repeat):\n{asked}")
    level = _level(body)
    note = LEVEL_NOTES[min(level, len(LEVEL_NOTES)) - 1]
    parts.append(f"Hint level {level}: {note}.")
    return "\n\n".join(parts)


async def sql_hint(ctx: RequestContext) -> Json:
    """One Socratic question; a reply with code or not one question is re-asked."""
    outage.ensure_available(ctx.now())
    body = ctx.body
    drill = wire(
        await engine_call(lambda sd: lambda: sd.get_drill(body["id"]), body["id"])
    )
    prompt, note = _hint_prompt(drill, body), ""
    for _ in range(RETRIES + 1):
        raw = await asyncio.to_thread(
            ask_model, HINT_SYSTEM, prompt + note, HINT_SCHEMA
        )
        question = str(raw.get("question", "")).strip()
        if (why := _problem(question, _level(body))) is None:
            return {"question": question}
        note = f"\n\nYour previous reply was rejected: {why}. Reply with ONE question."
    msg = "the model gave no usable hint; try again"
    raise RequestError(msg, code="model_error", retry=True)


def _generate_prompt(topic: str, difficulty: str, titles: list[str]) -> str:
    have = "; ".join(titles) or "none yet"
    return (
        f"Topic: {topic}\nDifficulty: {difficulty}\n"
        f"Existing drills on this topic (write a different one): {have}"
    )


def _blank(raw: dict[str, Any]) -> list[str]:
    return [
        k for k in SPEC_FIELDS if not (isinstance(raw.get(k), str) and raw[k].strip())
    ]


async def _save(spec: dict[str, str]) -> Json:
    made = await engine_call(lambda sd: lambda: sd.save_generated(spec))
    return wire(await engine_call(lambda sd: lambda: sd.get_drill(made), made))["meta"]


async def sql_generate(ctx: RequestContext) -> Json:
    """A new drill the engine has run and accepted; up to 2 re-asks on rejection."""
    outage.ensure_available(ctx.now())
    topic, difficulty = ctx.body["topic"], ctx.body["difficulty"]
    metas = wire(await engine_call(lambda sd: sd.list_drills, ensure=False))
    titles = [m["title"] for m in metas if m["topic"] == topic]
    prompt, note, reason = _generate_prompt(topic, difficulty, titles), "", ""
    for _ in range(RETRIES + 1):
        raw = await asyncio.to_thread(
            ask_model, GENERATE_SYSTEM, prompt + note, SPEC_SCHEMA
        )
        if blank := _blank(raw):
            reason = f"fields missing or blank: {', '.join(blank)}"
        else:
            spec = {k: raw[k] for k in SPEC_FIELDS} | {"topic": topic}
            try:
                return await _save(spec)
            except ValueError as exc:
                reason = str(exc)
                _logger.warning("generated drill rejected: %s", reason)
        note = f"\n\nYour previous drill was rejected: {reason}. Fix it."
    msg = f"the drill was rejected: {reason}"
    raise RequestError(msg, code="model_error", retry=True)
