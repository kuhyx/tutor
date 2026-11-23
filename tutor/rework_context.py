# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""What kuhy did on one LeetCode problem: the rework chat's context.

Display-only reads, never a gate input: leetcode-guard's
``history/<slug>.json`` and ``attempts.json`` (their shapes are documented
in the guard's ``_history_store`` and ``_attempt_model``) and the coach's own
``lc_sessions``. The rework chat (``tutor.relay.rework``) and a lesson on a
rework card (``tutor.prompt.for_source``) read it. Anyone can edit these
files, so every one may be missing, edited or corrupt: a bad file or row is
left out, a broken file with a warning. Everything is capped so the prompt
stays bounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Final
from urllib.parse import urlsplit

from tutor.store import data_dir

_logger = logging.getLogger(__name__)
SOURCE_HOST: Final = "https://rework.leetcode-coach.invalid"  # rework card sources
# A LeetCode titleSlug: it names a file of the guard's, so never ``../x``.
SLUG: Final = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.ASCII)
GUARD_ENV: Final = "TUTOR_GUARD_DATA"  # the guard's data dir (tests: tmp)
MAX_SUBMISSIONS: Final = 8  # newest first
MAX_CODE: Final = 1500  # characters of code per submission
MAX_DAYS: Final = 10
MAX_SESSIONS: Final = 3
MAX_TAIL: Final = 6  # chat entries per coach session
MAX_ENTRY: Final = 400
MAX_STATEMENT: Final = 3000
_BEAT: Final = 2  # a beat is [unix_seconds, tab]
NOTHING: Final = "No history of this problem on file."


@dataclass(frozen=True)
class History:
    """The context text and how many of each kind of record it holds."""

    text: str
    submissions: int
    days: int
    sessions: int

    def counts(self) -> dict[str, int]:
        """The wire's ``history`` object."""
        return {
            "submissions": self.submissions,
            "days": self.days,
            "sessions": self.sessions,
        }


def slug_of(source: str) -> str | None:
    """The problem of a rework card's ``SOURCE_HOST/<slug>/<hash>``; else None."""
    if not source.startswith(f"{SOURCE_HOST}/"):
        return None
    slug = urlsplit(source).path.split("/")[1]
    return slug if SLUG.fullmatch(slug) else None


def guard_dir() -> Path:
    """leetcode-guard's data dir (``TUTOR_GUARD_DATA`` overrides)."""
    found = os.environ.get(GUARD_ENV)
    return Path(found) if found else Path.home() / ".local/share/leetcode_guard"


def read_file(path: Path) -> object:
    """The file's JSON; ``None`` when it is missing or unreadable."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        _logger.warning("rework context: %s is unreadable: %s", path, err)
        return None


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " [...]"


def _num(value: object) -> int:
    return int(value) if isinstance(value, int | float) else 0


def dict_rows(value: object) -> list[dict[str, Any]]:
    """The dict rows of a list (or of a dict's values); anything else is none."""
    rows = list(value.values()) if isinstance(value, dict) else value
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _submissions(slug: str) -> list[str]:
    raw = read_file(guard_dir() / "history" / f"{slug}.json")
    rows = dict_rows(raw.get("submissions") if isinstance(raw, dict) else None)
    rows.sort(key=lambda r: _num(r.get("timestamp")), reverse=True)
    out = []
    for row in rows[:MAX_SUBMISSIONS]:
        at = _num(row.get("timestamp"))
        when = datetime.fromtimestamp(at).astimezone().date().isoformat() if at else "?"
        bits = [row.get(k) for k in ("status", "lang", "runtime", "memory")]
        line = " ".join([when, *(str(b) for b in bits if b)])
        code = row.get("code")
        if isinstance(code, str) and code:
            line += f"\n```\n{_cap(code, MAX_CODE)}\n```"
        out.append(line)
    return out


def _days(slug: str) -> list[str]:
    raw = read_file(guard_dir() / "attempts.json")
    found = dict_rows(raw.get("records") if isinstance(raw, dict) else None)
    mine = sorted(
        (r for r in found if r.get("slug") == slug),
        key=lambda r: str(r.get("day")),
        reverse=True,
    )
    out = []
    for rec in mine[:MAX_DAYS]:
        beats = [
            b for b in rec.get("beats") or [] if isinstance(b, list) and len(b) == _BEAT
        ]
        tabs = ", ".join(sorted({str(b[1]) for b in beats})) or "none"
        subs = [str(v.get("status")) for v in dict_rows(rec.get("submissions"))]
        out.append(
            f"{rec.get('day', '?')}: {len(beats)} beats ({tabs}); "
            f"submissions: {', '.join(subs) or 'none'}; "
            f"theory at solve: {rec.get('theory_at_solve') or '?'}"
        )
    return out


def sessions_of(slug: str) -> list[dict[str, Any]]:
    """Every coach session on ``slug``, newest first (the post-mortem reads all)."""
    folder = data_dir() / "lc_sessions"
    paths = sorted(folder.glob("*.json")) if folder.is_dir() else []
    found = [read_file(p) for p in paths]
    mine = [s for s in found if isinstance(s, dict) and s.get("slug") == slug]
    mine.sort(key=lambda s: _num(s.get("updated_ms")), reverse=True)
    return mine


def _sessions(slug: str) -> list[dict[str, Any]]:
    return sessions_of(slug)[:MAX_SESSIONS]


def _session_text(state: dict[str, Any]) -> str:
    lines = [f"Coach session ({state.get('phase')}, {state.get('title')})"]
    if state.get("belief"):
        lines.append(f"Opening belief: {state['belief']}")
    if state.get("last_code"):
        lines.append(f"Last code:\n```\n{_cap(str(state['last_code']), MAX_CODE)}\n```")
    for entry in dict_rows(state.get("thread"))[-MAX_TAIL:]:
        who = "kuhy" if entry.get("mine") else "coach"
        lines.append(f"{who}: {_cap(str(entry.get('md')), MAX_ENTRY)}")
    return "\n".join(lines)


def gather(slug: str) -> History:
    """Gather kuhy's history on ``slug`` (a valid titleSlug) as prompt text."""
    subs, days, sessions = _submissions(slug), _days(slug), _sessions(slug)
    parts = []
    statement = next(
        (str(s["statement_md"]) for s in sessions if s.get("statement_md")), ""
    )
    if statement:
        parts.append(f"Statement:\n{_cap(statement, MAX_STATEMENT)}")
    if subs:
        parts.append("Submissions, newest first:\n- " + "\n- ".join(subs))
    if days:
        parts.append("Days worked on it (browser beats):\n- " + "\n- ".join(days))
    parts.extend(_session_text(s) for s in sessions)
    return History("\n\n".join(parts) or NOTHING, len(subs), len(days), len(sessions))
