# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The two seams of the problem coach: ``leetcode_coach`` and the code runner.

Handlers only call :func:`coach` and :func:`runner`; tests :func:`install`
fakes. The real adapters below are the one place that knows the libraries'
module names (``leetcode_coach``, ``sql_drills``, ``code_runner``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from tutor.relay import lc_runner
from tutor.relay.lc_libs import lib as _lib
from tutor.relay.lc_protocol import ALGO_LANGS, SQL_LANGS
from tutor.store import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable

type Json = Any
type Box = Any  # leetcode_coach.toolbox.Toolbox, loaded late
type Ask = Callable[[str, str, dict[str, Any]], dict[str, Any]]
type Runner = Callable[[str, str, str, str], dict[str, Any]]
type Verdict = tuple[str, tuple[str, ...]]
type Toolbox = tuple[list[dict[str, Any]], dict[str, str]]
TOOLBOX_SLUG = "toolbox"
APKG_ONLY = "Anki desktop not open"  # make_cards.deliver's offline line


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


def _toolbox_path() -> Path:
    """The tutor's own toolbox, seeded from the library's on first use.

    ``append_entry`` writes its target: the library's copy sits in the frozen
    release's site-packages, which a deploy replaces, so confirmed entries
    would vanish. The data dir keeps them.
    """
    path = data_dir() / "lc_toolbox.json"
    if not path.exists():
        seed = Path(str(_lib("leetcode_coach.toolbox").TOOLBOX_PATH))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(seed.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _load_box() -> Box:
    return _lib("leetcode_coach.toolbox").load_safe(_toolbox_path())


def _verdict(statement: str, text: str, ask: Ask) -> Verdict:
    rc = _lib("leetcode_coach.req_check")
    got = rc.check(statement, text, _load_box(), ask)
    return str(got.verdict), tuple(got.missing)


def _toolbox() -> Toolbox:
    box = _load_box()
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


def _due_ms(day: str) -> int:
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=dt.UTC)
    return int(midnight.timestamp() * 1000)


def _due() -> list[dict[str, Any]]:
    return [
        {"slug": r["slug"], "title": r["slug"], "due_ms": _due_ms(r["due"])}
        for r in _lib("leetcode_coach.progress").due_retests()
    ]


def make_coach() -> Coach:
    """The real :class:`Coach` over ``leetcode_coach``."""
    return Coach(
        fetch=_problem,
        system_prompt=_system_prompt,
        check_req=_verdict,
        leaked=lambda reply, said: _lib("leetcode_coach.leak").leaked_names(
            reply, said, _load_box()
        ),
        toolbox=_toolbox,
        append_entry=lambda n, a, p: _lib("leetcode_coach.toolbox_cards").append_entry(
            n, a, p, path=_toolbox_path()
        ),
        deliver_anki=_deliver,
        log=_log,
        clusters=_clusters,
        due=_due,
    )


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
    """The code runner (the real one is ``lc_runner.run``)."""
    return cast("Runner", _ACTIVE.get("runner", lc_runner.run))
