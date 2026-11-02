# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The coach's mechanical gates (``DOCS-contract-coach.md`` "Gates"): pure, no I/O."""

from __future__ import annotations

import re
from typing import Final

BUDGET: Final = {"easy": 16, "medium": 24, "hard": 32}
MAX_TRIES: Final = 3
MAX_RUNG: Final = 3
CONFUSED_STOP: Final = 2
CHOICES: Final = ["write it", "hint!", "reveal"]
GATE_PREFIX: Final = {"algo": "req", "sql": "shape"}
_GATE: Final = re.compile(r"^\s*(req|shape)\s*:", re.IGNORECASE)
_FENCE: Final = re.compile(r"```.*?```", re.DOTALL)
_SPAN: Final = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
_SQL_STATEMENT: Final = re.compile(
    r"\bselect\b.+?\bfrom\b|\b(?:insert\s+into|delete\s+from)\b"
    r"|\bupdate\s+\w+\s+set\b|\bwith\s+\w+\s+as\s*\(",
    re.IGNORECASE | re.DOTALL,
)
_SQL_WORD: Final = re.compile(
    r"\b(?:select|from|where|group\s+by|join|case|when|having|union)\b",
    re.IGNORECASE,
)
_ALGO_CODE: Final = re.compile(
    r"=>|^\s*(?:function\b|def\s+\w+\s*\(|class\s+\w+|(?:const|let|var)\s+\w+\s*="
    r"|(?:for|while|if)\s*\(|import\s+\w)|[;{]\s*$|^\s*\}",
    re.MULTILINE,
)
_REFERS: Final = re.compile(
    r"\b(?:your\s+(?:query|code|solution|snippet|attempt|function|answer)"
    r"|the\s+(?:table|output|result|rows))\b",
    re.IGNORECASE,
)
_RUNG: Final = re.compile(r"H[0-3]")
_CIRCLES: Final = re.compile(r"going in circles|^\W*stop\W*$", re.IGNORECASE)
_CONFUSED: Final = re.compile(r"i\s+don.?t\s+understand|nie rozumiem", re.IGNORECASE)
_IMPERATIVE: Final = re.compile(
    r"^(try|write|predict|explain|tell|describe|trace|run|paste|list|sketch|walk|"
    r"show|give|say|name|work|think|check|change|fix|look|answer|type|fill|pick|do)\b",
    re.IGNORECASE,
)
_ROW: Final = re.compile(r"^\s*\|(.+)\|\s*$")
_SIGNATURE: Final = re.compile(
    r"(?:function\s*(\w*)|def\s+(\w+)|(\w+)\s*=\s*(?:function)?)\s*\(([^)]*)\)"
)


def gate_prefix(text: str) -> str | None:
    """``req`` or ``shape`` when the message opens with that label."""
    found = _GATE.match(text)
    return found.group(1).lower() if found else None


def is_code(text: str, kind: str) -> bool:
    """Whether a message is code: a fence, or a clear statement for this kind."""
    if _FENCE.search(text):
        return True
    if kind == "sql":
        return bool(_SQL_STATEMENT.search(text))
    return bool(_ALGO_CODE.search(text))


def output_columns(statement: str) -> list[str]:
    """The header of the statement's first ``Output:`` table, or ``[]``."""
    after = re.split(r"Output\s*:?\**", statement, maxsplit=1)
    for line in after[1].splitlines() if len(after) > 1 else []:
        if (row := _ROW.match(line)) is not None:
            return [c.strip() for c in row.group(1).split("|") if c.strip()]
    return []


def shape_verdict(statement: str, text: str) -> tuple[str, tuple[str, ...]]:
    """``(verdict, missing)``: ``text`` must name every output column."""
    columns = output_columns(statement)
    if not columns:
        return "unverified", ()
    said = text.lower()
    missing = tuple(c for c in columns if c.lower() not in said)
    return ("incomplete" if missing else "pass"), missing


def frustrated(text: str, confused: int) -> tuple[bool, int]:
    """Whether to stop and offer the 3 choices, and the new "don't understand" run."""
    if _CIRCLES.search(text):
        return True, 0
    if not _CONFUSED.search(text):
        return False, 0
    return confused + 1 >= CONFUSED_STOP, (confused + 1) % CONFUSED_STOP


def sentences(text: str) -> int:
    """How many sentences ``text`` has."""
    return len([s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s])


def _prose(reply: str) -> str:
    return _FENCE.sub("\n\n", reply)


def question_problem(reply: str) -> str | None:
    """Why the reply is not ONE question or instruction, or ``None``."""
    prose = re.sub(r"\"[^\"]*\"|“[^”]*”", "it", _prose(reply))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", prose) if p.strip()]
    if not paragraphs or prose.count("?") > 1:
        return "it asks more than one question; ask exactly one"
    last = re.sub(r"[*_>`()]", "", paragraphs[-1]).strip()
    final = [s for s in re.split(r"(?<=[.?!])\s+", last) if s][-1].strip()
    if final.endswith("?") or _IMPERATIVE.match(final):
        return None
    return "it must end on one question or one instruction"


def identifiers(starter: str, statement: str, kind: str) -> set[str]:
    """Names kuhy's code would use: starter signature, or table and column names."""
    names: set[str] = set()
    if kind == "sql":
        for line in statement.splitlines():
            if (row := _ROW.match(line)) is not None:
                names.update(c.strip() for c in row.group(1).split("|"))
            names.update(re.findall(r"Table:\s*(\w+)", line))
    for sig in _SIGNATURE.finditer(
        re.sub(r"/\*.*?\*/|//[^\n]*", "", starter, flags=re.DOTALL)
    ):
        names.update(n for n in sig.groups()[:3] if n)
        names.update(
            p.strip().split(":")[0].split("=")[0].strip().lstrip("*")
            for p in sig.group(4).split(",")
        )
    return {n for n in names if len(n) > 1 and re.fullmatch(r"\w+", n)}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def code_problem(reply: str, names: set[str], allowed: str, kind: str) -> str | None:
    """A snippet kuhy could paste: uses the problem's names and is not a quote."""
    seen = _squash(allowed)
    for span in _SPAN.findall(reply):
        body = span.strip("`").strip()
        body = body.split("\n", 1)[1] if "\n" in body else body
        shaped = (
            _SQL_WORD.search(body) if kind == "sql" else re.search(r"[(=]|\.\.\.", body)
        )
        if not shaped or not any(
            re.search(rf"\b{re.escape(n)}\b", body) for n in names
        ):
            continue
        if _squash(body) not in seen:
            shown = _squash(body)[:60]
            return f"it writes code kuhy could paste ({shown}); describe instead"
    return None


def rank(rung: str | None) -> int:
    """H0..H3 as 0..3; none as -1; ``ValueError`` for anything else."""
    if not rung:
        return -1
    if _RUNG.fullmatch(rung):
        return int(rung[1])
    raise ValueError(rung)


def rung_ceiling(current: int, *, hint: int, failed: bool) -> int:
    """The highest rung a reply may carry (``hint``: rungs climbed, 0-2)."""
    if hint:
        return 1 if current < 0 else min(current + hint, MAX_RUNG)
    return current + 1 if failed else current


def rung_problem(rung: str | None, ceiling: int) -> str | None:
    """Why the reply's rung tag is not allowed, or ``None``."""
    if rung and not _RUNG.fullmatch(rung):
        return "its rung must be H0, H1, H2, H3 or empty"
    wanted = rank(rung)
    if wanted > ceiling:
        return f"its rung H{wanted} climbs too fast; the ceiling is H{max(ceiling, 0)}"
    return None


def reprint(reply: str, last_code: str, last_table: str) -> str:
    """The reply plus kuhy's last code and result when it refers to them unshown."""
    if not _REFERS.search(reply):
        return reply
    extra = []
    if last_code and last_code.strip() not in reply:
        extra.append(f"Your last attempt:\n```\n{last_code.strip()}\n```")
    if last_table and last_table not in reply:
        extra.append(f"Last result:\n{last_table}")
    return "\n\n".join([reply, *extra])
