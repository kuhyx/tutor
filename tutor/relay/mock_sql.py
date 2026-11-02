# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The three SQL tasks of a mock: builtin and generated ``sql_drills`` drills.

Slots follow the test format: joins or aggregation, pivot, dates or number
formatting. The engine grades by exact output (``sd.run``); nothing here
touches a reference query. One generated drill is attempted per mock; when
the model or the engine refuses, a builtin one fills the slot.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import outage
from tutor.curriculum.modelcall import ask_model
from tutor.relay import sql_model
from tutor.relay.hooks import BASE_ERRORS
from tutor.relay.sql import engine_call, wire

if TYPE_CHECKING:
    import random

type Json = Any
_logger = logging.getLogger(__name__)
SLOTS: Final = (
    ("joins-null", "group-having"),
    ("pivot",),
    ("dates", "number-format"),
)
SAMPLE_ROWS: Final = 5


async def _metas() -> list[Json]:
    metas = wire(await engine_call(lambda sd: sd.list_drills, ensure=False))
    return [m for m in metas if m["kind"] == "write"]


async def _generate(topic: str) -> str | None:
    """Save one model-written drill on ``topic`` (``None`` when refused)."""
    prompt = f"Topic: {topic}\nDifficulty: medium\nExisting drills: write a new one."
    try:
        raw = await asyncio.to_thread(
            ask_model, sql_model.GENERATE_SYSTEM, prompt, sql_model.SPEC_SCHEMA
        )
        spec = {k: raw.get(k) for k in sql_model.SPEC_FIELDS}
        if not all(isinstance(v, str) and v.strip() for v in spec.values()):
            return None
        spec |= {"topic": topic, "kind": "write"}
        made = await engine_call(lambda sd: lambda: sd.save_generated(spec))
    except (*BASE_ERRORS, outage.ClaudeUnavailableError) as exc:
        _logger.warning("mock sql drill not generated: %s", exc)
        return None
    return str(made)


async def _drill(drill_id: str) -> Json:
    return wire(await engine_call(lambda sd: lambda: sd.get_drill(drill_id), drill_id))


def _untitled(task_md: str) -> str:
    """The task text without its ``# Title`` line (a title can name the tool)."""
    lines = task_md.lstrip().splitlines()
    return (
        "\n".join(lines[1:]).strip()
        if lines[:1] and lines[0].startswith("#")
        else task_md
    )


def _choose(
    metas: list[Json], topics: tuple[str, ...], seen: set[str], rnd: random.Random
) -> str:
    pool = [m for m in metas if m["topic"] in topics]
    fresh = [m for m in pool if m["id"] not in seen]
    return str(rnd.choice(fresh or pool)["id"])


async def pick(
    rnd: random.Random, seen: set[str], *, generate: bool = True
) -> tuple[list[Json], list[Json], list[str]]:
    """(public tasks, private records, notes) for the three SQL slots.

    ``generate=False`` (pre-built papers) never asks the model: all three
    drills are saved ones and no note is needed.
    """
    notes: list[str] = []
    metas = await _metas()
    slot3 = SLOTS[2][rnd.randrange(2)]
    made = await _generate(slot3) if generate else None
    if made is None and generate:
        notes.append("No new SQL drill this time: all three are saved ones.")
    ids = [
        made if i == len(SLOTS) - 1 and made else _choose(metas, topics, seen, rnd)
        for i, topics in enumerate(SLOTS)
    ]
    public: list[Json] = []
    private: list[Json] = []
    for n, drill_id in enumerate(ids, start=1):
        got = await _drill(drill_id)
        task = f"sq{n}"
        public.append(
            {
                "id": task,
                "section": "sql",
                "title": f"SQL task {n}",
                "topic": got["meta"]["topic"],
                "prompt_md": _untitled(got["task_md"]),
                "tables": got["tables"],
                "sample": got["expected_preview"][:SAMPLE_ROWS],
            }
        )
        private.append({"id": task, "drill": drill_id})
    return public, private, notes
