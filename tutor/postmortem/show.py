# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""An analysis as terminal text (the dry run's output; CLI output is free text)."""

from __future__ import annotations

from typing import Any


def _rate(pair: list[int]) -> str:
    done, total = pair
    return f"{done}/{total}" + (f" ({round(100 * done / total)}%)" if total else "")


def _problem(p: dict[str, Any]) -> list[str]:
    mins = "?" if p["minutes"] is None else p["minutes"]
    mark = "one-shot" if p["one_shot"] else "missed"
    head = (
        f"  {p['slug']}: {p['phase']}-theory, {p['tries']} tries, {mins} min, "
        f"hints {p['hints']}, {mark}"
    )
    out = [head]
    if p["used"] or p["skipped"]:
        out.append(f"    used {p['used']} skipped {p['skipped']}")
    if p["instead"]:
        out.append(f"    instead: {p['instead']}")
    if p["finding"]:
        out.append(f"    finding: {p['finding']}")
    return out


def _card(c: dict[str, Any]) -> list[str]:
    out = [f"  [{c['change']}] {c['id']}: {c['front']}"]
    if c["new_front"] or c["new_back"]:
        out.append(f"    -> Q: {c['new_front']} A: {c['new_back']}")
    if c["used_by"]:
        out.append(f"    used by one-shot: {', '.join(c['used_by'])}")
    if c["finding"]:
        out.append(f"    {c['finding']}")
    return out


def text(found: dict[str, Any]) -> str:
    """The report as plain lines."""
    shots = found["one_shot"]
    lines = [
        f"post-mortem {found['unit']} ({found['subject']})",
        (
            f"one-shot post-theory {_rate(shots['post'])}; "
            f"pre-theory {_rate(shots['pre'])}"
        ),
        f"problems ({len(found['problems'])}):",
    ]
    for problem in found["problems"]:
        lines += _problem(problem)
    lines.append("cards:")
    for card in found["cards"]:
        lines += _card(card)
    lines.append(f"new cards ({len(found['new_cards'])}):")
    lines += [f"  + Q: {c['front']} A: {c['back']}" for c in found["new_cards"]]
    lessons = found["lessons"]
    lines.append(f"lessons: {len(lessons['fix'])} fix, {len(lessons['keep'])} keep")
    lines += [f"  fix: {f['pattern']}" for f in lessons["fix"]]
    lines += [f"  keep: {k['card']}: {k['opening']}" for k in lessons["keep"]]
    future = sum(len(f.get("cards") or []) for f in found["future"])
    lines.append(f"future modules: {future} proposed cards")
    return "\n".join(lines)
