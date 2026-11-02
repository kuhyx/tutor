# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The two seams of the problem coach: ``leetcode_coach`` and the code runner.

Handlers only call :func:`coach` and :func:`runner`; tests :func:`install`
fakes. The real adapters below are the one place that knows the libraries'
module names (``leetcode_coach``, ``sql_drills``, ``code_runner``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import importlib.util
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from tutor.relay.errors import RequestError
from tutor.relay.lc_protocol import ALGO_LANGS, SQL_LANGS
from tutor.relay.sql import wire

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

_logger = logging.getLogger(__name__)
type Json = Any
type Ask = Callable[[str, str, dict[str, Any]], dict[str, Any]]
type Runner = Callable[[str, str, str, str], dict[str, Any]]
type Verdict = tuple[str, tuple[str, ...]]
type Toolbox = tuple[list[dict[str, Any]], dict[str, str]]
TOOLBOX_SLUG = "toolbox"


@dataclass(frozen=True)
class Problem:
    """A fetched problem; ``kind`` is ``sql`` or ``algo``."""

    slug: str
    title: str
    difficulty: str
    statement_md: str
    starter: dict[str, str] = field(default_factory=dict)
    kind: str = "algo"

    @property
    def langs(self) -> tuple[str, ...]:
        """The languages of this kind of problem; the first is the default."""
        return SQL_LANGS if self.kind == "sql" else ALGO_LANGS


@dataclass(frozen=True)
class Coach:
    """``leetcode_coach`` as blocking callables.

    ``fetch`` raises ``LookupError`` (premium or unknown) or ``OSError``;
    ``append_entry`` raises ``ValueError`` with the reason; ``check_req``
    returns (``pass|incomplete|unverified``, missing properties); ``toolbox``
    returns (entries of name, aliases, properties; property vocabulary).
    """

    fetch: Callable[[str], Problem]
    system_prompt: Callable[[str], str]
    check_req: Callable[[str, str, Ask], Verdict]
    leaked: Callable[[str, list[str]], list[str]]
    toolbox: Callable[[], Toolbox]
    append_entry: Callable[[str, list[str], list[str]], None]
    deliver_anki: Callable[[list[dict[str, str]]], str]
    log: Callable[..., None]
    clusters: Callable[[], list[dict[str, Any]]]
    due: Callable[[], list[dict[str, Any]]]


def _lib(name: str) -> ModuleType:
    if importlib.util.find_spec(name.split(".", maxsplit=1)[0]) is None:
        msg = f"{name.split('.', maxsplit=1)[0]} is not installed on the worker"
        raise RequestError(msg, code="worker_error")
    return importlib.import_module(name)


def _problem(arg: str) -> Problem:
    fp = _lib("leetcode_coach.fetch_problem")
    slug = fp.slug_from(arg)
    raw = fp.fetch(slug)
    if raw is None or raw.get("isPaidOnly") or not raw.get("content"):
        raise LookupError(slug)
    body = fp.render(raw, "mysql").split("\n## ", 1)[0].strip()
    starter = {s["langSlug"]: s["code"] for s in raw["codeSnippets"]}
    tags = {t["name"] for t in raw["topicTags"]}
    return Problem(
        slug,
        raw["title"],
        str(raw["difficulty"]).lower(),
        body,
        starter,
        "sql" if "Database" in tags else "algo",
    )


def _verdict(statement: str, text: str, ask: Ask) -> Verdict:
    rc, tb = _lib("leetcode_coach.req_check"), _lib("leetcode_coach.toolbox")
    got = rc.check(statement, text, tb.load_safe(), ask)
    return str(got.verdict), tuple(got.missing)


def _toolbox() -> Toolbox:
    box = _lib("leetcode_coach.toolbox").load_safe()
    entries = [
        {"name": e.name, "aliases": list(e.aliases), "properties": list(e.properties)}
        for e in box.entries
    ]
    return entries, dict(box.properties)


def _deliver(cards: list[dict[str, str]]) -> str:
    rules = _lib("leetcode_coach.card_rules")
    if problems := rules.validate(TOOLBOX_SLUG, cards):
        raise ValueError("; ".join(problems))
    return str(_lib("leetcode_coach.make_cards").deliver(TOOLBOX_SLUG, cards))


def _log(slug: str, event: str, **fields: object) -> None:
    sl = _lib("leetcode_coach.session_log")
    sl.append(sl.log_path(slug), event, **fields)


def _system_prompt(statement: str) -> str:
    pkg = Path(str(_lib("leetcode_coach").__file__)).parent
    skill = (pkg / "SKILL.md").read_text(encoding="utf-8")
    return str(_lib("leetcode_coach.local_prompt").system_prompt(skill, statement))


def _clusters() -> list[dict[str, Any]]:
    path = Path(str(_lib("leetcode_coach").__file__)).with_name("clusters.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"name": name, "problems": [p["slug"] for p in rows]}
        for name, rows in data["clusters"].items()
    ]


def _due() -> list[dict[str, Any]]:
    return [
        {"slug": r["slug"], "title": r["slug"], "due": r["due"]}
        for r in _lib("leetcode_coach.progress").due_retests()
    ]


def make_coach() -> Coach:
    """The real :class:`Coach` over ``leetcode_coach``."""
    return Coach(
        fetch=_problem,
        system_prompt=_system_prompt,
        check_req=_verdict,
        leaked=lambda reply, said: _lib("leetcode_coach.leak").leaked_names(
            reply, said, _lib("leetcode_coach.toolbox").load_safe()
        ),
        toolbox=_toolbox,
        append_entry=lambda n, a, p: _lib("leetcode_coach.toolbox_cards").append_entry(
            n, a, p
        ),
        deliver_anki=_deliver,
        log=_log,
        clusters=_clusters,
        due=_due,
    )


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
    sd = _lib("sql_drills")
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


def _run(lang: str, code: str, statement: str, starter: str) -> dict[str, Any]:
    if lang in SQL_LANGS:
        return _run_sql(lang, code, statement)
    cr = _lib("code_runner")
    if not (examples := cr.parse_examples(statement)):
        return {"ok": True, "no_examples": True, "examples": []}
    try:
        results = cr.run(lang, code, starter, examples)
    except cr.RunnerError as err:
        _logger.warning("code_runner refused the run: %s", err)
        return {"ok": False, "error": str(err), "examples": []}
    return {"ok": True, "examples": [_case(r) for r in results]}


_ACTIVE: dict[str, object] = {}


def install(coach_impl: Coach | None, runner_impl: Runner | None) -> None:
    """Use these backends (tests); ``None`` restores the real adapters."""
    _ACTIVE.clear()
    if coach_impl is not None:
        _ACTIVE["coach"] = coach_impl
    if runner_impl is not None:
        _ACTIVE["runner"] = runner_impl


def coach() -> Coach:
    """The coach library, or ``worker_error`` when it is missing."""
    if "coach" not in _ACTIVE:
        _lib("leetcode_coach")
        _ACTIVE["coach"] = make_coach()
    return cast("Coach", _ACTIVE["coach"])


def runner() -> Runner:
    """The code runner (the real one is :func:`_run`)."""
    return cast("Runner", _ACTIVE.get("runner", _run))
