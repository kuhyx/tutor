# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from tutor.relay import lc_backend as b
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from pathlib import Path


class BoomError(Exception):
    pass


def ns(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def fake_libs(monkeypatch: pytest.MonkeyPatch, **libs: Any) -> None:
    monkeypatch.setattr(b, "_lib", lambda name: libs[name])


def test_lib_imports_an_installed_package() -> None:
    assert b._lib("json").__name__ == "json"
    with pytest.raises(RequestError, match="nothing_here"):
        b._lib("nothing_here.sub")


def case(n: int, ok: bool, error: str | None = None) -> SimpleNamespace:
    return ns(n=n, ok=ok, input={"a": 1}, expected=[1], actual=[2], error=error)


def test_algo_runner_maps_code_runner_results(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run(lang: str, code: str, starter: str, examples: list[Any]) -> list[Any]:
        seen["args"] = (lang, code, starter, examples)
        if code == "crash":
            msg = "no entry point"
            raise BoomError(msg)
        return [case(1, True), case(2, False), case(3, False, "TimeLimitExceeded")]

    cr = ns(
        parse_examples=lambda text: [text] if "Input" in text else [],
        run=run,
        RunnerError=BoomError,
    )
    fake_libs(monkeypatch, code_runner=cr)
    assert b._run("python3", "x", "plain", "def f(): ...") == {
        "ok": True,
        "no_examples": True,
        "examples": [],
    }
    got = b._run("python3", "x", "Input", "def f(): ...")
    assert got["examples"][0] == {
        "n": 1,
        "ok": True,
        "input": '{"a": 1}',
        "expected": "[1]",
    }
    assert got["examples"][1]["got"] == "[2]"
    assert got["examples"][2]["error"] == "TimeLimitExceeded"
    assert seen["args"][2] == "def f(): ..."
    bad = b._run("python3", "crash", "Input", "")
    assert (bad["ok"], bad["error"]) == (False, "no entry point")


def test_sql_runner_maps_run_problem_results(monkeypatch: pytest.MonkeyPatch) -> None:
    from sql_drills import RunResult

    calls: list[str] = []

    class NoExamplesError(Exception):
        pass

    def ensure(dialect: str) -> None:
        calls.append(dialect)

    def run_problem(statement: str, code: str, dialect: str) -> list[Any]:
        if code == "none":
            raise NoExamplesError
        if code == "down":
            msg = "docker"
            raise BoomError(msg)
        ok = RunResult(True, None, ["a"], [["1"]], [["1"]], True)
        bad = RunResult(False, "ERROR: column", [], [], [["1"]], False)
        return [ok, bad] if code == "mixed" else [ok]

    sd = ns(
        ensure_running=ensure,
        run_problem=run_problem,
        NoExamplesError=NoExamplesError,
        EngineError=BoomError,
        DialectError=BoomError,
        ProblemUnavailableError=BoomError,
    )
    fake_libs(monkeypatch, sql_drills=sd)
    assert b._run("mysql", "none", "st", "")["no_examples"] is True
    with pytest.raises(RuntimeError, match="docker"):
        b._run("postgresql", "down", "st", "")
    fine = b._run("postgresql", "ok", "st", "")
    assert (fine["ok"], fine["examples"][0]["n"]) == (True, 1)
    mixed = b._run("mysql", "mixed", "st", "")
    assert mixed["ok"] is False
    assert mixed["error"] == "ERROR: column"
    assert [e["ok"] for e in mixed["examples"]] == [True, False]
    assert calls == ["mysql", "postgresql", "postgresql", "mysql"]


QUESTION = {
    "title": "Two Sum",
    "difficulty": "Easy",
    "content": "x",
    "isPaidOnly": False,
    "codeSnippets": [{"langSlug": "python3", "code": "def f(): ..."}],
    "topicTags": [{"name": "Array"}],
}


def lib_tree(tmp_path: Path) -> SimpleNamespace:
    (tmp_path / "SKILL.md").write_text("skill text", encoding="utf-8")
    (tmp_path / "clusters.json").write_text(
        '{"clusters": {"bits": [{"slug": "missing-number"}]}}', encoding="utf-8"
    )
    return ns(__file__=str(tmp_path / "__init__.py"))


def test_problem_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    questions = {
        "two-sum": QUESTION,
        "paid": {**QUESTION, "isPaidOnly": True},
        "gone": None,
    }
    fp = ns(
        slug_from=lambda arg: arg.rsplit("/", 1)[-1],
        fetch=lambda slug: questions[slug],
        render=lambda q, lang: (
            "# 1. Two Sum\nbody\n\n## Starter code\nx\n## Site hints\ny"
        ),
    )
    fake_libs(monkeypatch, **{"leetcode_coach.fetch_problem": fp})
    got = b._problem("two-sum")
    assert (got.slug, got.title, got.difficulty, got.kind) == (
        "two-sum",
        "Two Sum",
        "easy",
        "algo",
    )
    assert got.statement_md == "# 1. Two Sum\nbody"
    assert got.starter == {"python3": "def f(): ..."}
    questions["db"] = {**QUESTION, "topicTags": [{"name": "Database"}]}
    assert b._problem("db").kind == "sql"
    for slug in ("paid", "gone"):
        with pytest.raises(LookupError):
            b._problem(slug)


def test_coach_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = ns(name="XOR", aliases=("^",), properties=("p",))
    box = ns(entries=(entry,), properties={"p": "meaning"})
    log_calls: list[Any] = []
    appended: list[Any] = []
    delivered: list[str] = []

    def deliver(slug: str, cards: list[Any]) -> str:
        delivered.append(slug)
        return "done"

    libs = {
        "leetcode_coach": lib_tree(tmp_path),
        "leetcode_coach.toolbox": ns(load_safe=lambda: box),
        "leetcode_coach.req_check": ns(
            check=lambda st, text, tb, ask: ns(verdict="incomplete", missing=["p"])
        ),
        "leetcode_coach.card_rules": ns(
            validate=lambda slug, cards: [] if cards[0]["front"] else ["empty front"]
        ),
        "leetcode_coach.make_cards": ns(deliver=deliver),
        "leetcode_coach.session_log": ns(
            log_path=lambda slug: f"/log/{slug}",
            append=lambda path, event, **f: log_calls.append((path, event, f)),
        ),
        "leetcode_coach.local_prompt": ns(
            system_prompt=lambda skill, st: f"{skill}|{st}"
        ),
        "leetcode_coach.progress": ns(
            due_retests=lambda: [{"slug": "a", "due": "2026-11-01"}]
        ),
        "leetcode_coach.leak": ns(leaked_names=lambda reply, said, tb: [reply, *said]),
        "leetcode_coach.toolbox_cards": ns(
            append_entry=lambda n, a, p: appended.append((n, a, p))
        ),
    }
    fake_libs(monkeypatch, **libs)
    coach = b.make_coach()
    assert coach.check_req("st", "req: x", lambda *a: {}) == ("incomplete", ("p",))
    assert coach.toolbox() == (
        [{"name": "XOR", "aliases": ["^"], "properties": ["p"]}],
        {"p": "meaning"},
    )
    assert coach.deliver_anki([{"front": "f", "back": "b"}]) == "done"
    assert delivered == ["toolbox"]
    with pytest.raises(ValueError, match="empty front"):
        coach.deliver_anki([{"front": "", "back": "b"}])
    coach.log("two-sum", "rung", rung="H1")
    assert log_calls == [("/log/two-sum", "rung", {"rung": "H1"})]
    assert coach.system_prompt("st") == "skill text|st"
    assert coach.clusters() == [{"name": "bits", "problems": ["missing-number"]}]
    assert coach.due() == [{"slug": "a", "title": "a", "due": "2026-11-01"}]
    assert coach.leaked("reply", ["said"]) == ["reply", "said"]
    coach.append_entry("n", [], ["p"])
    assert appended == [("n", [], ["p"])]


def test_coach_and_runner_accessors(monkeypatch: pytest.MonkeyPatch) -> None:
    b.install(None, None)
    monkeypatch.setattr(b, "_lib", lambda name: None)
    sentinel = object()
    monkeypatch.setattr(b, "make_coach", lambda: sentinel)
    assert b.coach() is sentinel
    assert b.coach() is sentinel
    assert b.runner() is b._run
    b.install(None, None)
