# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Grading one task of a mock at ``finish`` (keys and hidden tests live here)."""

from __future__ import annotations

import asyncio
from typing import Any, Final

from tutor.relay import mock_palin
from tutor.relay.sql import engine_call, wire

type Json = Any
MAX_FAILED: Final = 3


def palin(priv: Json) -> mock_palin.PalinTask:
    """The palindrome variant a mock stored."""
    return next(t for t in mock_palin.TASKS if t.key == priv["palin"])


def _mcq_item(pub: Json, priv: Json, given: str) -> tuple[bool, Json]:
    chosen = (
        int(given) if given.isdigit() and int(given) < len(pub["options"]) else None
    )
    detail = {
        "options": pub["options"],
        "correct_option": priv["key"],
        "chosen": chosen,
        "output": pub["options"][priv["key"]],
    }
    return chosen == priv["key"], detail


async def _sql_item(priv: Json, given: str) -> tuple[bool, Json]:
    if not given.strip():
        return False, {"error": "No answer."}
    got = wire(
        await engine_call(
            lambda sd: lambda: sd.run(priv["drill"], given), priv["drill"]
        )
    )
    keys = ["error", "columns", "rows", "expected_rows", "cell_diff"]
    keys += ["extra_rows", "missing_rows"]
    ok = bool(got.get("ok")) and bool(got.get("match"))
    return ok, {k: got.get(k) for k in keys}


async def _code_item(priv: Json, given: str) -> tuple[bool, Json]:
    if not given.strip():
        return False, {"passed": 0, "total": 0, "failed": [], "error": "No answer."}
    results = await asyncio.to_thread(mock_palin.run, palin(priv), given, hidden=True)
    failed = [r for r in results if not r["ok"]]
    detail = {
        "passed": len(results) - len(failed),
        "total": len(results),
        "failed": failed[:MAX_FAILED],
    }
    return not failed, detail


async def grade(pub: Json, priv: Json, given: str) -> Json:
    """The result item of one task: verdict, detail and a review link."""
    if pub["section"] == "py_mcq":
        ok, detail = _mcq_item(pub, priv, given)
    elif pub["section"] == "sql":
        ok, detail = await _sql_item(priv, given)
    else:
        ok, detail = await _code_item(priv, given)
    item: Json = {
        "id": pub["id"],
        "section": pub["section"],
        "title": pub["title"],
        "topic": pub["topic"],
        "correct": ok,
        "answer": given or None,
        "detail": detail,
    }
    if not ok and pub["section"] == "sql":
        item["link"] = {"kind": "lesson", "topic": pub["topic"]}
    if not ok and pub["section"] == "py_code":
        item["link"] = {"kind": "coach", "slug": palin(priv).slug}
    return item
