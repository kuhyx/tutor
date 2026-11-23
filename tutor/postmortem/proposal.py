# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The bodies of the two todo tasks a post-mortem can file.

- ``Apply post-mortem <unit>: future modules + skills``: every proposed card
  per future module and the skill proposal. A normal task: todoImplementer's
  spec stage is kuhy's approval, and after it ``python -m tutor
  apply-postmortem <unit>`` applies the future-module part.
- ``Post-mortem <unit> failed``: the error and the retry command, the only
  way back in (no automatic retry).
"""

from __future__ import annotations

from typing import Any, Final

_PAIR: Final = 2


def _rate(pair: object) -> str:
    if not isinstance(pair, list) or len(pair) != _PAIR or not pair[1]:
        return "n/a"
    return f"{pair[0]}/{pair[1]} ({round(100 * pair[0] / pair[1])}%)"


def apply_title(unit: str) -> str:
    """The approval task's title."""
    return f"Apply post-mortem {unit}: future modules + skills"


def apply_body(entry: dict[str, Any]) -> str:
    """Markdown: the rate, the proposed cards per future module, the skills diff."""
    unit, rev = entry["unit"], entry["rev"]
    rate = _rate(entry["one_shot"]["post"])
    lines = [
        f"Post-theory one-shot rate of `{unit}` (revision {rev}): {rate}.",
        "",
        "Earlier units: "
        + (
            ", ".join(f"{e['unit']} {_rate(e['post'])}" for e in entry["earlier"])
            or "none"
        ),
        "",
        "## Future modules",
        "",
        (
            "Approve, trim or change the cards below, then run "
            f"`python -m tutor apply-postmortem {unit}`: it regenerates every "
            "listed module with no taught card (the drafter already reads "
            "`lessons.json`), then adds the approved cards."
        ),
    ]
    for future in entry["future"]:
        lines += ["", f"### {future['module']}", ""]
        lines += [
            f"- Q: {c.get('front', '')} A: {c.get('back', '')} ({c.get('why', '')})"
            for c in future.get("cards") or []
        ] or ["- (no card proposed)"]
    lines += ["", "## Skills and generation", "", entry["skills_md"] or "(none)"]
    return "\n".join(lines)


def failed_title(unit: str) -> str:
    """The failure task's title."""
    return f"Post-mortem {unit} failed"


def retry_command(unit: str) -> str:
    """The shell command that clears the failed marker (the live tutor's python)."""
    return (
        "cd ~/.local/lib/tutor-live/current && "
        f"~/src/tutor/.venv/bin/python -m tutor postmortem {unit} --retry"
    )


def failed_body(unit: str, rev: int, error: str) -> str:
    """Markdown: what failed and the one command that tries again."""
    return "\n".join(
        [
            f"The post-mortem of `{unit}` (revision {rev}) failed: {error}",
            "",
            "Nothing changed: no card, report, lesson or revision row was written.",
            "The worker does not retry on its own. To run it again:",
            "",
            f"    {retry_command(unit)}",
        ]
    )
