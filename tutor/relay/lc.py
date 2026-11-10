# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``lc_list``, ``lc_open``, ``lc_run`` (``DOCS-contract-coach.md``)."""

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING, Any, Final

from tutor import codes, outage
from tutor.relay import lc_backend, lc_reply, lc_state
from tutor.relay.errors import RequestError
from tutor.relay.lc_prompt import OPENER
from tutor.relay.lc_protocol import SQL_LANGS

if TYPE_CHECKING:
    from tutor.relay.context import RequestContext

type Json = Any
MAX_LIST: Final = 200
NO_EXAMPLES: Final = "[cannot run this problem's examples locally: test it on LeetCode]"
RUNNER_DOWN: Final = (RuntimeError, OSError, TimeoutError)


def _bad(msg: str) -> RequestError:
    return RequestError(msg, code="bad_request")


def _now_ms(ctx: RequestContext) -> int:
    return int(ctx.now() * 1000)


def _table_md(columns: list[str], rows: list[list[str]]) -> str:
    head = "| " + " | ".join(columns) + " |\n|" + "---|" * len(columns)
    return "\n".join([head, *("| " + " | ".join(r) + " |" for r in rows[:10])])


SUGGESTED: Final[dict[str, Json]] = {
    "name": "palindromes-dp",
    "problems": [
        "longest-palindromic-subsequence",
        "longest-palindromic-substring",
        "palindromic-substrings",
        "valid-palindrome",
        "valid-palindrome-ii",
        "longest-palindrome",
        "minimum-insertion-steps-to-make-a-string-palindrome",
    ],
}


async def lc_list(ctx: RequestContext) -> Json:
    """Recent sessions, suggested + coach clusters, cold re-tests due (no model)."""
    del ctx
    coach = lc_backend.coach()
    return {
        "recent": lc_state.recent(),
        "clusters": [SUGGESTED, *await asyncio.to_thread(coach.clusters)],
        "due": await asyncio.to_thread(coach.due),
    }


async def _problem(body: dict[str, Any]) -> lc_backend.Problem:
    if body["statement"] is not None:
        statement = str(body["statement"])
        slug = "paste-" + hashlib.sha256(statement.encode()).hexdigest()[:8]
        kind = "sql" if body["lang"] in SQL_LANGS else "algo"
        title = body["title"] or "Pasted problem"
        return lc_backend.Problem(slug, title, "medium", statement, {}, kind)
    if body["problem"] is None:
        msg = "lc_open needs problem, statement or lc_id"
        raise _bad(msg)
    try:
        return await asyncio.to_thread(lc_backend.coach().fetch, body["problem"])
    except LookupError:
        msg = "that problem has no public statement; paste it"
        raise RequestError(
            msg, code="bad_request", extra={"reason": codes.PASTE_STATEMENT}
        ) from None
    except OSError as err:
        msg = f"LeetCode is unreachable: {err}"
        raise RequestError(msg, code="worker_error", retry=True) from err
    except ValueError as err:
        raise _bad(str(err)) from err


def _shown(lc_id: str, state: lc_state.State) -> dict[str, Any]:
    return {
        "lc_id": lc_id,
        "slug": state["slug"],
        "title": state["title"],
        "difficulty": state["difficulty"],
        "kind": state["kind"],
        "lang": state["lang"],
        "langs": list(lc_state.langs_of(state)),
        "statement_md": state["statement_md"],
        "starter": state["starter"],
        "model": lc_state.MODEL,
        "retest": False,
        "state": lc_state.view(state),
    }


async def lc_open(ctx: RequestContext) -> Json:
    """Start a session (fetch, opener) or resume one with its stored chat."""
    body = ctx.body
    if body["lc_id"] is not None:
        state = lc_state.load(body["lc_id"])
        return {**_shown(body["lc_id"], state), "thread": state["thread"]}
    problem = await _problem(body)
    lang = body["lang"] or problem.langs[0]
    if lang not in problem.langs:
        msg = f"{lang} is not a language of this {problem.kind} problem"
        raise _bad(msg)
    outage.ensure_available(ctx.now())
    meta = {
        "slug": problem.slug,
        "title": problem.title,
        "difficulty": problem.difficulty,
        "kind": problem.kind,
        "statement_md": problem.statement_md,
        "starter": problem.starter,
    }
    lc_id, state = lc_state.fresh(meta, lang, _now_ms(ctx))
    lc_reply.log(state, "session_start", app="tutor", lang=lang)
    got = await lc_reply.ask_reply(state, OPENER, lc_reply.Rules(-1))
    lc_state.say(state, mine=False, md=got["reply_md"])
    lc_state.save(lc_id, state, _now_ms(ctx))
    lc_reply.heartbeat()
    return {**_shown(lc_id, state), "reply_md": got["reply_md"]}


def _cut(report: dict[str, Any]) -> dict[str, Any]:
    if len(report["examples"]) > MAX_LIST:
        report["examples"] = report["examples"][:MAX_LIST]
        report["truncated"] = True
    return report


def _after_run(state: lc_state.State, code: str, report: dict[str, Any]) -> None:
    """Record the run on ``state``."""
    examples = report["examples"]
    full = bool(examples) and report["ok"] and all(e.get("ok") for e in examples)
    first = next((e for e in examples if not e.get("ok") and e.get("rows")), None)
    if first is not None:
        state["last_table"] = _table_md(first.get("columns", []), first["rows"])
    if not state["code_seen"]:
        lc_reply.log(state, "code")
    state.update(
        code_seen=True,
        last_code=code,
        failed=not (full or report["no_examples"]),
        ran_ok=state["ran_ok"] or full,
        no_examples=state.get("no_examples", False) or report["no_examples"],
        runs=state.get("runs", 0) + 1,
    )


async def lc_run(ctx: RequestContext) -> Json:
    """Run kuhy's code on the statement's examples (model-free)."""
    body = ctx.body
    lc_id, state = body["lc_id"], lc_state.load(body["lc_id"])
    if body["lang"] not in lc_state.langs_of(state):
        msg = f"{body['lang']} is not a language of this {state['kind']} problem"
        raise _bad(msg)
    gate = state["gate"]
    if not gate["open"]:
        note = "[code held back: pass the requirement list first]"
        return {"state": lc_state.view(state), "held": True, "note": note}
    try:
        raw = await asyncio.to_thread(
            lc_backend.runner(),
            body["lang"],
            body["code"],
            state["statement_md"],
            state["starter"].get(body["lang"], ""),
        )
    except RUNNER_DOWN as err:
        msg = f"the code runner failed: {err}"
        raise RequestError(msg, code="worker_error", retry=True) from err
    report = {"ok": True, "examples": [], **raw}
    report["no_examples"] = bool(raw.get("no_examples")) or (
        report["ok"] and not report["examples"]
    )
    passed = sum(1 for e in report["examples"] if e.get("ok"))
    total = len(report["examples"])
    _after_run(state, body["code"], report)
    lc_state.save(lc_id, state, _now_ms(ctx))
    lc_reply.heartbeat()
    extra = {"note": NO_EXAMPLES} if report["no_examples"] else {}
    return {
        **extra,
        **_cut(report),
        "passed": passed,
        "total": total,
        "state": lc_state.view(state),
    }
