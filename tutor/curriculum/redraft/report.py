# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The proof a redraft run leaves: ``report.md``.

Before and after for every card the learner had flagged, the per-rule
violation counts (the code checks over every live card before and now; the
separate audit judge's first pass and what was published), every old card
suspended without a successor per subject (taught ones marked), the modules
that were cut, and the failed modules. Read from ``redraft/`` and the
subjects as they are now; writing it changes nothing else.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from tutor.curriculum import quality
from tutor.curriculum.redraft import run
from tutor.curriculum.subject_store import read_json

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.curriculum.records import CardRec
    from tutor.curriculum.redraft.run import Before, Unit


def default_path(started_ms: int) -> Path:
    """``~/.local/state/tutor/redraft/<start time>/report.md``."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(started_ms / 1000))
    return Path.home() / ".local/state/tutor/redraft" / stamp / "report.md"


def _code(cards: dict[str, CardRec], hard: set[str]) -> dict[str, int]:
    live = [(cid, c) for cid, c in cards.items() if not c.suspended]
    return quality.counts(
        [
            quality.problems(c.front, c.back, c.mnemonic, hard=cid in hard)
            for cid, c in live
        ]
    )


def _add(total: dict[str, int], more: dict[str, int]) -> None:
    for rule, n in more.items():
        total[rule] = total.get(rule, 0) + n


def _face(card: CardRec | None) -> str:
    if card is None or card.suspended:
        return "(no successor: the card is suspended)"
    aid = f"\n  - mnemonic: {card.mnemonic}" if card.mnemonic else ""
    return f"rev {card.rev}\n  - Q: {card.front}\n  - A: {card.back}{aid}"


def _out(ctx: Context, unit: Unit) -> dict[str, Any]:
    raw = read_json(run.root(ctx) / "out" / unit.subject / f"{unit.module}.json", {})
    return raw if isinstance(raw, dict) else {}


def _flagged(snap: Before, now: dict[str, CardRec]) -> list[str]:
    lines = []
    for cid, reasons in snap.flags.items():
        old = snap.cards[cid]
        lines += [
            f"### `{snap.subject}` / `{cid}`",
            *(f"- flag: {r}" for r in reasons),
            f"- before: rev {old.rev}\n  - Q: {old.front}\n  - A: {old.back}",
            f"- after: {_face(now.get(cid))}",
            "",
        ]
    return lines


def _table(title: str, rows: dict[str, dict[str, int]]) -> list[str]:
    rules = [*quality.RULE_IDS, "no_verdict"]
    head = "| " + " | ".join(["", *rules]) + " |"
    lines = [f"## {title}", "", head, "|" + "---|" * (len(rules) + 1)]
    for name, counts in rows.items():
        cells = [str(counts.get(r, 0)) for r in rules]
        lines.append("| " + " | ".join([name, *cells]) + " |")
    return [*lines, ""]


def _units(ctx: Context, snap: Before, mine: list[Unit]) -> dict[str, Any]:
    """What the subject's built units add up to (audit counts, lost, cut)."""
    first: dict[str, int] = {}
    published: dict[str, int] = {}
    lost: list[str] = []
    cut: list[str] = []
    for unit in mine:
        out = _out(ctx, unit)
        audit = out.get("audit") or {}
        _add(first, audit.get("first_pass") or {})
        _add(published, audit.get("published") or {})
        swap = out.get("swap") or {}
        lost += [
            f"- `{cid}`{' (taught)' if cid in snap.taught else ''}: "
            f"{snap.cards[cid].front}"
            for cid in swap.get("suspended", [])
        ]
        if len(swap.get("modules", [])) > 1:
            cut.append(f"- `{unit.name}` -> {', '.join(swap['modules'])}")
    return {"first": first, "published": published, "lost": lost, "cut": cut}


def _subject(ctx: Context, subject: str, mine: list[Unit]) -> dict[str, Any]:
    """Everything the report says about one subject."""
    snap = run.before(ctx, subject)
    now = ctx.subjects.cards(subject)
    hard_now = {c for c in snap.hard if c in now and not now[c].suspended}
    live_before = sum(not c.suspended for c in snap.cards.values())
    live_now = sum(not c.suspended for c in now.values())
    kept = sum(c in now and not now[c].suspended for c in snap.taught)
    return {
        "flagged": _flagged(snap, now),
        "before": _code(snap.cards, snap.hard),
        "now": _code(now, hard_now),
        **_units(ctx, snap, mine),
        "line": f"| `{subject}` | {live_before} | {live_now} | "
        f"{len(snap.taught)} | {kept} |",
    }


def render(ctx: Context) -> str:
    """The report as markdown."""
    units = run.units(ctx)
    subjects = list(dict.fromkeys(u.subject for u in units))
    parts = {
        s: _subject(ctx, s, [u for u in units if u.subject == s]) for s in subjects
    }
    failed = [u for u in units if u.state != run.DONE]
    done = sum(u.state == run.DONE for u in units)
    lines = [
        "# Redraft report",
        "",
        f"{done} of {len(units)} modules redrafted; {len(failed)} not done.",
        "",
        (
            "| subject | live cards before | live cards now | taught before | "
            "taught and still live |"
        ),
        "|---|---|---|---|---|",
        *(p["line"] for p in parts.values()),
        "",
        "## The flagged cards, before and after",
        "",
        *(line for p in parts.values() for line in p["flagged"]),
    ]
    for title, key in (
        ("Rule violations before (code checks, live cards)", "before"),
        ("Rule violations now (code checks, live cards)", "now"),
        ("Audit judge, first pass (repaired or dropped since)", "first"),
        ("Audit judge, published cards", "published"),
    ):
        lines += _table(title, {s: p[key] for s, p in parts.items()})
    lines += ["## Old cards suspended without a successor", ""]
    for subject, part in parts.items():
        lines += [f"### `{subject}` ({len(part['lost'])})", *part["lost"], ""]
    lines += ["## Modules cut into several", ""]
    lines += [line for p in parts.values() for line in p["cut"]] or ["(none)"]
    lines += ["", "## Modules not redrafted", ""]
    lines += [f"- `{u.name}` ({u.state}): {u.error}" for u in failed] or ["(none)"]
    return "\n".join(lines) + "\n"


def write(ctx: Context, out: Path | None = None) -> Path:
    """Write the report (default: :func:`default_path`); returns its path."""
    raw = read_json(run.root(ctx) / "run.json", {})
    started = raw.get("started") if isinstance(raw, dict) else None
    text = render(ctx)
    target = out or default_path(int(started or 0))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target
