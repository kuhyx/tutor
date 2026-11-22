# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""``rework_open`` / ``rework_turn``: the lock's ``?`` on one LeetCode problem.

leetcode-guard opens ``/rework/<subject>/<module>/<slug>``; kuhy says what
was unclear and the tutor answers and adds up to :data:`MAX_CARDS` cards to
that module. That is all it does. The new cards are untaught, so
``module_state``'s reconcile writes the signed not-done row by itself, and
that row sends the lock back to THEORY. Nothing here writes module_state or
marks a card taught.

A card's source is ``SOURCE_HOST/<slug>/<hash of its front>``, seeded with a
line built from the card, as ``lc_cards`` does for the toolbox. One URL per
card, because ``sources.seed_text`` never overwrites a cached page. Its
``tutor`` mark records ``"source": "rework:<slug>"``. The history in the
prompt is display-only (``rework_context``).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import TYPE_CHECKING, Any, Final

from tutor import outage, rework_context, sources
from tutor.curriculum import card_ops, module_state
from tutor.curriculum.errors import RequestError as CurriculumError
from tutor.curriculum.modelcall import ask_model
from tutor.relay.errors import RequestError
from tutor.store import data_dir

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.curriculum.context import Context
    from tutor.curriculum.records import Module
    from tutor.relay.context import RequestContext

_logger = logging.getLogger(__name__)
type State = dict[str, Any]
SOURCE_HOST: Final = rework_context.SOURCE_HOST
MAX_CARDS: Final = 5
KEEP_THREAD: Final = 40
_BREAK: Final = re.compile(r"[.!?](?=\s)")  # quote's sentence break: one sentence
SYSTEM: Final = (
    "You are kuhy's tutor in a rework chat. He just solved, or tried, a LeetCode "
    "problem and says what was unclear about it. Find the gap in the theory "
    "behind his words and his history on the problem; answer in a few short "
    "paragraphs of markdown, and never write a full solution. cards: 0-5 new "
    "flashcards that close that gap, for the module named below: front a "
    "question of at most 25 words, back one sentence of at most 30 words. "
    "Only cards the module does not already hold; none while you still need "
    "to ask him what he meant."
)
SCHEMA: Final = {
    "type": "object",
    "properties": {
        "reply_md": {"type": "string"},
        "cards": {
            "type": "array",
            "maxItems": MAX_CARDS,
            "items": {
                "type": "object",
                "properties": {"front": {"type": "string"}, "back": {"type": "string"}},
                "required": ["front", "back"],
            },
        },
    },
    "required": ["reply_md", "cards"],
}


def _bad(msg: str) -> RequestError:
    return RequestError(msg, code="bad_request")


def rework_id(subject: str, module: str, slug: str) -> str:
    """One chat per (subject, module, slug): opening it again resumes it."""
    return hashlib.sha256(f"{subject}/{module}/{slug}".encode()).hexdigest()[:12]


def _path(rid: str) -> Path:
    return data_dir() / "rework_sessions" / f"{rid}.json"


def _target(cur: Context, subject: str, module: str) -> Module:
    """The module the guard named; refused unless a gated subject's plan has it."""
    if subject not in module_state.SUBJECTS:
        msg = f"{subject} is not a LeetCode subject"
        raise _bad(msg)
    plan = cur.subjects.plan(subject)
    found = plan.module(module) if plan else None
    if found is None:
        msg = f"{subject} has no module {module!r}"
        raise _bad(msg)
    return found


def _load(rid: str) -> State | None:
    """The stored chat; ``None`` for an unknown id (the worker wrote every file)."""
    path = _path(rid)
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    return state if isinstance(state, dict) else None


def _save(rid: str, state: State, now_ms: int) -> None:
    state["thread"] = state["thread"][-KEEP_THREAD:]
    state["updated_ms"] = now_ms
    path = _path(rid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(path)


def _shown(rid: str, state: State, module: Module) -> dict[str, Any]:
    history = rework_context.gather(state["slug"])
    return {
        "rework_id": rid,
        "subject": state["subject"],
        "module": state["module"],
        "module_title": module.title,
        "slug": state["slug"],
        "thread": state["thread"],
        "cards": state["cards"],
        "history": history.counts(),
    }


async def rework_open(ctx: RequestContext) -> dict[str, Any]:
    """Open (or resume) the chat on a problem; no model call."""
    body, cur = ctx.body, ctx.engine.ctx
    module = _target(cur, body["subject"], body["module"])
    rid = rework_id(body["subject"], body["module"], body["slug"])
    state = await asyncio.to_thread(_load, rid)
    if state is None:
        now = int(ctx.now() * 1000)
        state = {**{k: body[k] for k in ("subject", "module", "slug")}, "thread": []}
        state.update(cards=[], created_ms=now)
        await asyncio.to_thread(_save, rid, state, now)
    return _shown(rid, state, module)


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _prompt(state: State, module: Module, cur: Context, text: str) -> str:
    history = rework_context.gather(state["slug"]).text
    held = [
        c.front
        for c in cur.subjects.cards(state["subject"]).values()
        if c.module == module.id and not c.suspended
    ]
    tail = "\n".join(
        f"{'kuhy' if e['mine'] else 'tutor'}: {e['md']}" for e in state["thread"][-12:]
    )
    return "\n\n".join(
        [
            f"Problem: {state['slug']}",
            f"Module: {module.title}. {module.summary}",
            "Cards the module holds:\n- " + "\n- ".join(held),
            f"kuhy's history on the problem:\n{history}",
            f"Conversation so far:\n{tail}",
            f"kuhy: {text}",
        ]
    )


def _add(cur: Context, state: State, wanted: list[Any]) -> tuple[list[Any], list[Any]]:
    """Add the model's cards; returns (added, refused). Duplicates are skipped."""
    subject, slug = state["subject"], state["slug"]
    have = {_norm(c.front) for c in cur.subjects.cards(subject).values()}
    added: list[dict[str, str]] = []
    refused: list[dict[str, str]] = []
    for raw in [c for c in wanted if isinstance(c, dict)][:MAX_CARDS]:
        front, back = (
            str(raw.get("front", "")).strip(),
            str(raw.get("back", "")).strip(),
        )
        if not front or not back or _norm(front) in have:
            continue
        have.add(_norm(front))
        url = f"{SOURCE_HOST}/{slug}/{hashlib.sha256(front.encode()).hexdigest()[:8]}"
        sources.seed_text(url, _BREAK.sub(";", f"Rework of {slug}: {front} {back}"))
        draft = card_ops.Draft(
            state["module"],
            front,
            back,
            url,
            f"{front} {back}",
            code_built=True,
            origin=f"rework:{slug}",
        )
        try:
            cid, _ = card_ops.add(cur, subject, draft)
        except CurriculumError as err:
            _logger.warning("rework card %r refused: %s", front, err.message)
            refused.append({"front": front, "reason": err.message})
            continue
        added.append({"id": cid, "front": front, "back": back})
    return added, refused


async def rework_turn(ctx: RequestContext) -> dict[str, Any]:
    """Send kuhy's words to the tutor: a reply and the cards it adds."""
    body, cur = ctx.body, ctx.engine.ctx
    rid = body["rework_id"]
    state = await asyncio.to_thread(_load, rid)
    if state is None:
        msg = f"unknown rework chat {rid!r}"
        raise _bad(msg)
    module = _target(cur, state["subject"], state["module"])
    outage.ensure_available(ctx.now())
    prompt = await asyncio.to_thread(_prompt, state, module, cur, body["text"])
    raw = await asyncio.to_thread(ask_model, SYSTEM, prompt, SCHEMA)
    reply = str(raw.get("reply_md") or "")
    added, refused = await asyncio.to_thread(_add, cur, state, raw.get("cards") or [])
    state["thread"] += [
        {"mine": True, "md": body["text"]},
        {"mine": False, "md": reply},
    ]
    state["cards"] += added
    await asyncio.to_thread(_save, rid, state, int(ctx.now() * 1000))
    return {
        "reply_md": reply,
        "cards": added,
        "refused": refused,
        "added": len(state["cards"]),
    }
