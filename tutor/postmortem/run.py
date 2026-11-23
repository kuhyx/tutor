# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The analysis: measure every solve, ask the draft tier once, merge the answer.

Code decides what code can: tries, one-shot, pre/post theory, the one-shot
rate and which cards are KEPT (a card whose idea a post-theory one-shot solve
used; with no such solve, any one-shot solve). The model only names ideas
used and skipped, findings, edits, suspensions, new cards, lessons and the
proposals. A kept card is never edited or suspended, whatever the model says.
No retry: one call; a failure raises to the caller (``watch``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor.postmortem import deck, evidence, lessons, prompt

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.postmortem.evidence import Request, Solve

type Analysis = dict[str, Any]


def _rate(solves: list[Solve], *, post: bool) -> list[int]:
    mine = [s for s in solves if s.post == post and s.ac_at is not None]
    return [sum(s.one_shot for s in mine), len(mine)]


def _by(rows: object, key: str) -> dict[str, dict[str, Any]]:
    found = rows if isinstance(rows, list) else []
    return {str(r.get(key)): r for r in found if isinstance(r, dict)}


def _strs(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _problems(solves: list[Solve], raw: dict[str, Any], ids: set[str]) -> list[Any]:
    said = _by(raw.get("problems"), "slug")
    out = []
    for found in solves:
        model = said.get(found.slug, {})
        out.append(
            {
                **found.row(),
                "used": [c for c in _strs(model.get("used")) if c in ids],
                "skipped": [c for c in _strs(model.get("skipped")) if c in ids],
                "instead": str(model.get("instead") or ""),
                "finding": str(model.get("finding") or ""),
            }
        )
    return out


def kept_cards(problems: list[dict[str, Any]]) -> tuple[dict[str, list[str]], str]:
    """Card id -> the one-shot solves that used it; and which solves counted."""
    shots = [p for p in problems if p["one_shot"] and p["phase"] == "post"]
    basis = "post"
    if not shots:
        shots, basis = [p for p in problems if p["one_shot"]], "any"
    used: dict[str, list[str]] = {}
    for found in shots:
        for cid in found["used"]:
            used.setdefault(cid, []).append(found["slug"])
    return used, basis


def _cards(
    cards: list[deck.Card], raw: dict[str, Any], kept: dict[str, Any]
) -> list[Any]:
    said = _by(raw.get("cards"), "id")
    out = []
    for card in cards:
        model = said.get(card.id, {})
        verdict = str(model.get("verdict") or "ok")
        change = "kept" if card.id in kept else verdict
        if change == "edit" and not (model.get("front") or model.get("back")):
            change = "ok"  # an edit with no new text changes nothing
        out.append(
            {
                "id": card.id,
                "module": card.module,
                "front": card.front,
                "taught": card.taught,
                "again": card.again,
                "change": "same" if change == "ok" else change,
                "finding": str(model.get("finding") or ""),
                "used_by": kept.get(card.id, []),
                "new_front": str(model.get("front") or "") if change == "edit" else "",
                "new_back": str(model.get("back") or "") if change == "edit" else "",
            }
        )
    return out


def analyse(ctx: Context, request: Request) -> Analysis:
    """The merged analysis of ``request``; raises whatever the model call raises."""
    done_at = evidence.theory_done_at(ctx.data_dir, request.subject, request.modules)
    solves = [evidence.solve_of(s, done_at) for s in request.solves]
    solves.sort(key=lambda s: s.ac_at or 0)
    cards = deck.unit_cards(ctx, request.subject, request.modules)
    future = deck.future_modules(ctx, request.subject, request.modules)
    about = {
        "modules": deck.module_text(ctx, request.subject, request.modules),
        "future": future,
        "lessons": lessons.text(request.subject),
    }
    text = prompt.build(request, solves, cards, about)
    raw = ctx.draft(prompt.SYSTEM, text, prompt.SCHEMA)
    problems = _problems(solves, raw, {c.id for c in cards})
    kept, basis = kept_cards(problems)
    future_ids = {f["module"] for f in future}
    return {
        "unit": request.unit,
        "subject": request.subject,
        "modules": list(request.modules),
        "theory_done_at": done_at,
        "one_shot": {
            "post": _rate(solves, post=True),
            "pre": _rate(solves, post=False),
        },
        "kept_basis": basis,
        "problems": problems,
        "cards": _cards(cards, raw, kept),
        "new_cards": [
            {
                "front": str(c.get("front") or ""),
                "back": str(c.get("back") or ""),
                "why": str(c.get("why") or ""),
                "slugs": _strs(c.get("slugs")),
            }
            for c in raw.get("new_cards") or []
            if isinstance(c, dict) and c.get("front") and c.get("back")
        ],
        "lessons": lessons.clean(raw.get("lessons"), set(kept)),
        "future": [
            f
            for f in raw.get("future") or []
            if isinstance(f, dict) and f.get("module") in future_ids
        ],
        "skills_md": str(raw.get("skills_md") or ""),
        "seen": sorted(request.solves),
    }
