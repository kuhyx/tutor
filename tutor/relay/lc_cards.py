# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``lc_cards``: the post-mortem property -> operation cards, into FSRS and Anki."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor import outage, sources
from tutor.curriculum import card_ops
from tutor.curriculum.modelcall import ask_model
from tutor.curriculum.records import Meta, Module, Plan
from tutor.curriculum.subject_store import Change
from tutor.relay import lc_backend, lc_prompt, lc_reply, lc_state
from tutor.relay.errors import RequestError

if TYPE_CHECKING:
    from tutor.curriculum.context import Context
    from tutor.relay.context import RequestContext

_logger = logging.getLogger(__name__)
SUBJECT: Final = "leetcode-toolbox"
MODULE: Final = "toolbox"
SOURCE_HOST: Final = "https://toolbox.leetcode-coach.invalid"
ANKI_DOWN: Final = (OSError, ValueError, RuntimeError, LookupError)
ASK: Final = (
    "Post-mortem. entries: the toolbox operations this problem needed, exactly as "
    "named in the toolbox. proposals: an operation the problem needed that the "
    "toolbox lacks, with properties taken ONLY from the property vocabulary."
)


def _ensure_subject(ctx: Context) -> None:
    if ctx.subjects.meta(SUBJECT) is not None:
        return
    goal = "Property to operation cards from the LeetCode coach's toolbox."
    module = Module(MODULE, "Toolbox", "Which operation has these properties.")
    module.status = "ready"
    plan = Plan(1, "approved", "", [module])
    meta = Meta("LeetCode toolbox", goal, "active", ctx.clock())
    ctx.subjects.commit(SUBJECT, meta, Change(plan=plan, cards={}))


def _card(entry: dict[str, Any]) -> dict[str, str]:
    front = "Toolbox: " + ", ".join(entry["properties"]) + "?"
    return {"front": front, "back": str(entry["name"])}


def _fsrs(ctx: Context, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _ensure_subject(ctx)
    have = {rec.front: cid for cid, rec in ctx.subjects.cards(SUBJECT).items()}
    rows: list[dict[str, Any]] = []
    for entry in entries:
        card = _card(entry)
        props = "; ".join(entry["properties"])
        name = entry["name"]
        line = f"In the toolbox, the operation {name} has these properties: {props}."
        hint = f"toolbox operation {name} properties {props}"
        slug = "-".join(str(entry["name"]).lower().split())
        url = f"{SOURCE_HOST}/{slug}"
        sources.seed_text(url, line)
        new = card["front"] not in have
        if new:
            draft = card_ops.Draft(MODULE, card["front"], card["back"], url, hint)
            have[card["front"]], _ = card_ops.add(ctx, SUBJECT, draft)
        rows.append({"id": have[card["front"]], **card, "new": new})
    return rows


async def _anki(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not entries:
        return {"delivered": False, "line": "no cards"}
    cards = [_card(e) for e in entries]
    try:
        line = await asyncio.to_thread(lc_backend.coach().deliver_anki, cards)
    except ANKI_DOWN as err:
        _logger.warning("Anki delivery failed: %r", err)
        return {"delivered": False, "line": str(err)}
    # No AnkiConnect: the library wrote an .apkg that still needs importing.
    return {"delivered": lc_backend.APKG_ONLY not in line, "line": line}


def _known(box: lc_backend.Toolbox, names: list[str]) -> list[dict[str, Any]]:
    by_name = {}
    for entry in box[0]:
        for alias in [entry["name"], *entry["aliases"]]:
            by_name[" ".join(alias.casefold().split())] = entry
    found = [by_name.get(" ".join(n.casefold().split())) for n in names]
    return [e for i, e in enumerate(found) if e is not None and e not in found[:i]]


async def _propose(
    state: lc_state.State, box: lc_backend.Toolbox
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prompt = (
        f"{ASK}\n\nProblem:\n{state['statement_md']}\n\n"
        f"kuhy's requirement lists: {json.dumps(state['reqs'])}\n"
        f"kuhy's code:\n{state['last_code']}\n\n"
        f"Toolbox: {json.dumps(box[0])}\nProperty vocabulary: {json.dumps(box[1])}"
    )
    system = lc_prompt.system(lc_backend.coach().system_prompt(state["statement_md"]))
    raw = await asyncio.to_thread(ask_model, system, prompt, lc_prompt.CARDS_SCHEMA)
    known = _known(box, [str(n) for n in raw.get("entries", [])])
    taken = {n.casefold() for e in box[0] for n in [e["name"], *e["aliases"]]}
    proposals = [
        {"name": p["name"], "aliases": p["aliases"], "properties": p["properties"]}
        for p in raw.get("proposals", [])
        if p["properties"]
        and set(p["properties"]) <= set(box[1])
        and str(p["name"]).casefold() not in taken
    ]
    return known, proposals


async def _confirmed(
    confirm: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    coach, refused, names = lc_backend.coach(), [], []
    for entry in confirm:
        try:
            await asyncio.to_thread(
                coach.append_entry, entry["name"], entry["aliases"], entry["properties"]
            )
        except ValueError as err:
            _logger.warning("toolbox entry %r refused: %s", entry["name"], err)
            refused.append({"name": entry["name"], "reason": str(err)})
        else:
            names.append(entry["name"])
    return _known(coach.toolbox(), names), refused


async def lc_cards(ctx: RequestContext) -> dict[str, Any]:
    """Cards for the toolbox entries a finished problem used (and new proposals)."""
    lc_id, confirm = ctx.body["lc_id"], ctx.body["confirm"]
    state = lc_state.load(lc_id)
    if state["phase"] != "done":
        msg = "finish the exit explanation first"
        raise RequestError(msg, code="bad_request")
    proposals: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    if confirm:
        entries, refused = await _confirmed(confirm)
    else:
        outage.ensure_available(ctx.now())
        box = await asyncio.to_thread(lc_backend.coach().toolbox)
        entries, proposals = await _propose(state, box)
    rows = await asyncio.to_thread(_fsrs, ctx.engine.ctx, entries)
    anki = await _anki(entries)
    lc_reply.log(state, "postmortem", cards=len(rows))
    lc_reply.heartbeat()
    return {
        "state": lc_state.view(state),
        "cards": rows,
        "proposals": proposals,
        "refused": refused,
        "fsrs": {
            "added": sum(r["new"] for r in rows),
            "existing": sum(not r["new"] for r in rows),
        },
        "anki": anki,
    }
