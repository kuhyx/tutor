# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The signed report (every revision of a unit) and C7, the revision rows.

``postmortems/<subject>/<unit>.json`` is one signed document::

    {"kind": "postmortem_report", "subject": ..., "unit": ...,
     "revisions": [{"rev": 1, "at": ..., "one_shot": {"post": [k, n], ...},
                    "earlier": [...], "problems": [...], "cards": [...],
                    "applied": {...}, "lessons": {...}, "future": [...],
                    "skills_md": "...", "seen": [...]}],
     "hmac": "..."}

``revisions.json`` (C7) holds one signed row per applied revision; the guard
reads it to pay ``theory-redone:<subject>:<module>:<rev>`` once the re-pass
lands (``DOCS-contract-postmortem.md``).
"""

from __future__ import annotations

from typing import Any, Final

from tutor.postmortem import files, signed

KIND: Final = "postmortem_report"


def load(subject: str, unit: str) -> dict[str, Any] | None:
    """The unit's signed report, if any."""
    doc = signed.read_doc(files.report_path(subject, unit))
    return doc if doc and doc.get("kind") == KIND else None


def revisions(subject: str, unit: str) -> list[dict[str, Any]]:
    """Every revision of the unit's report, oldest first."""
    doc = load(subject, unit)
    found = doc.get("revisions") if doc else None
    return [r for r in found if isinstance(r, dict)] if isinstance(found, list) else []


def seen(subject: str, unit: str) -> set[str]:
    """Every solve an earlier post-mortem of the unit analysed."""
    return {str(s) for r in revisions(subject, unit) for s in r.get("seen") or []}


def everything() -> list[dict[str, Any]]:
    """Every signed report on file (all subjects), oldest revision first."""
    folder = files.root()
    paths = sorted(folder.glob("*/*.json")) if folder.is_dir() else []
    mine = [p for p in paths if p.parent.name not in files.OWN_DIRS]
    docs = [signed.read_doc(p) for p in mine if p.name != "lessons.json"]
    return [d for d in docs if d and d.get("kind") == KIND]


def earlier(unit: str) -> list[dict[str, Any]]:
    """The post-theory one-shot rate of every other unit's latest revision."""
    out = []
    for doc in everything():
        found = [r for r in doc.get("revisions") or [] if isinstance(r, dict)]
        if doc.get("unit") == unit or not found:
            continue
        last = found[-1]
        rate = (last.get("one_shot") or {}).get("post")
        out.append({"unit": doc.get("unit"), "rev": last.get("rev"), "post": rate})
    return out


def save(subject: str, unit: str, entry: dict[str, Any]) -> bool:
    """Append ``entry`` as the next revision; whether it was written."""
    doc = {
        "kind": KIND,
        "subject": subject,
        "unit": unit,
        "revisions": [*revisions(subject, unit), entry],
    }
    return signed.write_doc(files.report_path(subject, unit), doc)


def record_revision(found: dict[str, Any], rev: int, at: float) -> bool:
    """Append the signed C7 row of revision ``rev``; whether it was written."""
    unit = found["unit"]
    row = {
        "kind": files.REV_KIND,
        "entry_id": f"pm:{found['subject']}:{unit}:{rev}",
        "day": signed.local_day(at),
        "detail": {
            "unit": unit,
            "subject": found["subject"],
            "modules": list(found["modules"]),
            "rev": rev,
            "at": at,
        },
    }
    return signed.append_row(files.revisions_path(), row) is not None
