# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``postmortems/<subject>/lessons.json``: what every post-mortem taught, signed.

Two kinds per post-mortem: ``fix`` (a pattern future cards must cover or
avoid) and ``keep`` (the shape of a card that worked: its opening question,
toy example and length). The card drafter reads them on every draft of the
subject (``draft_prompt.prompt``), with no approval step (kuhy, 2026-11-23).
Signed so an edit is ignored rather than steering the drafter; a missing or
forged file is no lessons.
"""

from __future__ import annotations

from typing import Any, Final

from tutor.postmortem import files, signed

KIND: Final = "postmortem_lessons"
MAX_TEXT: Final = 6000  # characters in a draft prompt


def _str(value: object) -> str:
    return " ".join(str(value).split()) if value else ""


def clean(raw: object, kept: set[str]) -> dict[str, list[dict[str, Any]]]:
    """The model's lessons, normalised; a ``keep`` only for a kept card."""
    found = raw if isinstance(raw, dict) else {}
    fix = [
        {"pattern": _str(f.get("pattern")), "why": _str(f.get("why"))}
        for f in found.get("fix") or []
        if isinstance(f, dict) and f.get("pattern")
    ]
    keep = [
        {
            "card": _str(k.get("card")),
            "opening": _str(k.get("opening")),
            "toy": _str(k.get("toy")),
            "words": k.get("words") if isinstance(k.get("words"), int) else 0,
            "why": _str(k.get("why")),
        }
        for k in found.get("keep") or []
        if isinstance(k, dict) and k.get("card") in kept
    ]
    return {"fix": fix, "keep": keep}


def entries(subject: str) -> list[dict[str, Any]]:
    """Every post-mortem's lessons for ``subject``, oldest first."""
    doc = signed.read_doc(files.lessons_path(subject))
    rows = doc.get("entries") if doc and doc.get("kind") == KIND else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def record(subject: str, entry: dict[str, Any]) -> bool:
    """Append ``entry`` (``unit``, ``rev``, ``fix``, ``keep``); whether it was saved."""
    doc = {"kind": KIND, "subject": subject, "entries": [*entries(subject), entry]}
    return signed.write_doc(files.lessons_path(subject), doc)


def text(subject: str) -> str:
    """The lessons as draft-prompt text; ``""`` when there are none."""
    lines: list[str] = []
    for entry in entries(subject):
        unit = entry.get("unit", "?")
        lines += [
            f"- FIX ({unit}): {f['pattern']} ({f['why']})"
            for f in entry.get("fix") or []
        ]
        lines += [
            f"- KEEP ({unit}): open like {k['opening']!r}, toy example "
            f"{k['toy']!r}, about {k['words']} words ({k['why']})"
            for k in entry.get("keep") or []
        ]
    if not lines:
        return ""
    body = "\n".join(lines)
    return body if len(body) <= MAX_TEXT else body[-MAX_TEXT:]
