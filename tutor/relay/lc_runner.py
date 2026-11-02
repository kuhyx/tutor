# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Run kuhy's code on the statement's examples: ``sql_drills`` / ``code_runner``."""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from tutor.relay.lc_libs import lib
from tutor.relay.lc_protocol import SQL_LANGS
from tutor.relay.sql import wire

_logger = logging.getLogger(__name__)


class _CaseLike(Protocol):
    n: int
    ok: bool
    input: object
    expected: object
    actual: object
    error: str | None


def _shown(value: object) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)[:200]


def _case(result: _CaseLike) -> dict[str, Any]:
    case: dict[str, Any] = {
        "n": result.n,
        "ok": result.ok,
        "input": _shown(result.input),
        "expected": _shown(result.expected),
    }
    if result.error:
        case["error"] = str(result.error)
    elif not result.ok:
        case["got"] = _shown(result.actual)
    return case


def _run_sql(lang: str, code: str, statement: str) -> dict[str, Any]:
    sd = lib("sql_drills")
    try:
        sd.ensure_running(dialect=lang)
        results = sd.run_problem(statement, code, dialect=lang)
    except sd.NoExamplesError as err:
        _logger.warning("no examples parsed from the statement: %s", err)
        return {"ok": True, "no_examples": True, "examples": []}
    except (sd.EngineError, sd.DialectError, sd.ProblemUnavailableError) as err:
        raise RuntimeError(str(err)) from err
    cases = [
        {"n": i, "ok": r.ok and r.match, **wire(r)} for i, r in enumerate(results, 1)
    ]
    errors = [str(c["error"]) for c in cases if c.get("error")]
    return {"ok": not errors, "error": errors[0] if errors else None, "examples": cases}


def run(lang: str, code: str, statement: str, starter: str) -> dict[str, Any]:
    """Run ``code`` in ``lang`` on the statement's examples (the wire report)."""
    if lang in SQL_LANGS:
        return _run_sql(lang, code, statement)
    cr = lib("code_runner")
    if not (examples := cr.parse_examples(statement)):
        return {"ok": True, "no_examples": True, "examples": []}
    try:
        results = cr.run(lang, code, starter, examples)
    except cr.RunnerError as err:
        _logger.warning("code_runner refused the run: %s", err)
        return {"ok": False, "error": str(err), "examples": []}
    return {"ok": True, "examples": [_case(r) for r in results]}
