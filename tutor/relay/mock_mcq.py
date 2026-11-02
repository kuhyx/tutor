# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Python "what does this print" questions with a key from really running them.

The model writes snippet plus three wrong outputs; the right option is the
snippet's own stdout from ``code_runner``'s sandbox, so the key is real and a
snippet that errors, hangs or prints nothing is dropped. A seed bank (also
verified by a test) and a cache of earlier verified questions fill up when
the model is down or gives too few.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Final

import code_runner as cr

from tutor import outage
from tutor.curriculum.modelcall import STRING, array_of, ask_model, strict_object
from tutor.relay.hooks import BASE_ERRORS
from tutor.relay.mock_seeds import SEEDS
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path
    import random

type Json = Any
_logger = logging.getLogger(__name__)
COUNT: Final = 10
ASK: Final = 12
MAX_CODE: Final = 1200
MAX_OUT: Final = 160
WRONG: Final = 3
_ITEM: Final = strict_object(
    {"topic": STRING, "code": STRING, "wrong_outputs": array_of(STRING)}
)
SCHEMA: Final = strict_object({"questions": array_of(_ITEM)})
SYSTEM: Final = (
    "You write Python 3.14 'what does this print' multiple-choice questions "
    "for a timed test. Each: a short deterministic snippet (3-10 lines, no "
    "input, no randomness, no imports beyond the standard library, no "
    "time/dates) that prints exactly what a careful reader can work out; "
    "`topic` is two words. `wrong_outputs`: three plausible but different "
    "wrong outputs a student might pick from a classic misconception "
    "(mutable defaults, slicing, scope, integer division, sort stability, "
    "dict order, string methods, comprehension, generators, rounding, "
    "copy vs reference). Do not state the right output."
)
_PROBE: Final = "\n\ndef _probe(x):\n    return x\n"


def _bank() -> Path:
    return data_dir() / "mock_bank.json"


def snippet_output(code: str) -> str | None:
    """The sandboxed stdout of ``code``, or ``None`` if it fails or times out."""
    example = cr.Example(1, {"x": 0}, 0)
    result = cr.run("python3", code + _PROBE, "def _probe(x):", [example])[0]
    return result.stdout.strip() if result.ok else None


def verify(topic: str, code: str, wrong: list[str]) -> Json | None:
    """A question whose key is the real output, or ``None`` if unusable."""
    if not code.strip() or len(code) > MAX_CODE:
        return None
    out = snippet_output(code)
    if not out or len(out) > MAX_OUT:
        return None
    distinct: list[str] = []
    for item in (w.strip() for w in wrong):
        if item and item != out and item not in distinct and len(item) <= MAX_OUT:
            distinct.append(item)
    if len(distinct) < WRONG:
        return None
    return {"topic": topic.strip()[:40] or "python", "code": code.strip(),
            "correct": out, "wrong": distinct[:WRONG]}  # fmt: skip


def _read_cache() -> list[Json]:
    try:
        data = json.loads(_bank().read_text(encoding="utf-8"))
    except OSError, ValueError:
        _logger.warning("mock bank unreadable; starting empty")
        return []
    return data if isinstance(data, list) else []


def _write_cache(items: list[Json]) -> None:
    path = _bank()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[-200:]), encoding="utf-8")


def _verified(raw: list[Json]) -> list[Json]:
    out: list[Json] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        wrong = item.get("wrong_outputs")
        got = verify(
            str(item.get("topic", "")),
            str(item.get("code", "")),
            [str(w) for w in wrong] if isinstance(wrong, list) else [],
        )
        if got is not None and all(got["code"] != q["code"] for q in out):
            out.append(got)
    return out


async def generate() -> list[Json]:
    """Fresh verified questions from the model (may be fewer than asked)."""
    raw = await asyncio.to_thread(ask_model, SYSTEM, f"Write {ASK} questions.", SCHEMA)
    items = raw.get("questions")
    if not isinstance(items, list):
        return []
    return await asyncio.to_thread(_verified, items)


def seeds() -> list[Json]:
    """The built-in bank, verified on use (a drifted seed is dropped)."""
    return _verified(
        [
            {"topic": s["topic"], "code": s["code"], "wrong_outputs": s["wrong"]}
            for s in SEEDS
        ]
    )


async def assemble(rnd: random.Random, now: float) -> tuple[list[Json], list[str]]:
    """``COUNT`` verified questions (fresh model ones first) and notes."""
    notes: list[str] = []
    fresh: list[Json] = []
    try:
        outage.ensure_available(now)
        fresh = await generate()
    except (
        *BASE_ERRORS,
        outage.ClaudeUnavailableError,
    ) as exc:  # the model must never block a mock
        _logger.warning("mock mcq generation failed: %s", exc)
        notes.append("Model unavailable: questions come from the saved bank.")
    if fresh:
        _write_cache([*_read_cache(), *fresh])
    pool = list(fresh)
    if len(pool) < COUNT:
        rest = [*_read_cache(), *await asyncio.to_thread(seeds)]
        seen = {q["code"] for q in pool}
        rnd.shuffle(rest)
        for q in rest:
            if q["code"] not in seen and len(pool) < COUNT:
                pool.append(q)
                seen.add(q["code"])
    return pool[:COUNT], notes
