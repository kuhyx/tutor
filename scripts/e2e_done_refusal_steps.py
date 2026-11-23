#!/usr/bin/env python3
# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Agent-E2E flow F31's steps: queue the model, send, assert (``e2e_done_refusal``)."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Final

from e2e_failures import _await, _send
from e2e_flow import Flow, FlowError, State
from e2e_follow_up import COMPOSER, _events
import e2e_script_session as script

from tutor import done_refusal
from tutor.curriculum.context import Context

OPEN: Final = "Tell me what you already know about this card."


def queue(flow: Flow) -> Path:
    """The scripted model's queue file (beside the data dir)."""
    return Path(flow.args.data).parent / "model_script.json"


def taught(flow: Flow, subject: str) -> set[str]:
    """The taught card ids of ``subject`` (the fold of the sandbox log)."""
    return Context(flow.args.data).fold().taught_ids(subject)


def theory_rows(flow: Flow) -> int:
    """How many ``theory-done`` rows the sandbox ledger holds."""
    path = flow.args.data / "ledger.json"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return text.count("theory-done")


def start(flow: Flow, subject: str, body: dict[str, Any]) -> dict[str, Any]:
    """A second device's ``session_start`` (one opening turn queued)."""
    script.write(queue(flow), [{"message": OPEN}])
    flow.step(f"session_start {body}")
    rid = _send(flow, "session_start", {"subject": subject, **body})
    return _await(flow, rid, 30)


def candidates(flow: Flow, subject: str) -> list[tuple[str, str]]:
    """(card, a required card) pairs: the card untaught, its requires taught."""
    done = taught(flow, subject)
    cards = Context(flow.args.data).subjects.cards(subject)
    return [
        (cid, rec.requires[-1])
        for cid, rec in cards.items()
        if rec.requires and cid not in done and set(rec.requires) <= done
    ]


def mark(flow: Flow, subject: str, card: str, *, done: bool) -> None:
    """A second device's ``card_done`` request for ``card``; refused fails."""
    flow.step(f"a second device marks {card} done={done}")
    body = {"subject": subject, "card": card, "done": done}
    if not _await(flow, _send(flow, "card_done", body)).get("ok"):
        msg = f"card_done {card} {done} was refused"
        raise FlowError(msg)


def waived_pick(flow: Flow, subject: str) -> tuple[str, str, list[str]]:
    """A card of a granted module with an untaught require in a refused one.

    Returns the card, that require, and its other untaught requires (in granted
    modules: the flow teaches them first). The grant is the sandbox's C3 row.
    """
    row = json.loads((Path(flow.args.data).parent / "theory_phase.json").read_text())
    granted = {m for s, m in row["detail"]["teachable"] if s == subject}
    cards, done = Context(flow.args.data).subjects.cards(subject), taught(flow, subject)
    for cid, rec in cards.items():
        if rec.module not in granted or rec.suspended:
            continue
        held = [r for r in rec.requires if r not in done]
        if waived := [r for r in held if cards[r].module not in granted]:
            return cid, waived[0], [r for r in held if r not in waived]
    msg = f"no card of {sorted(granted)} needs an untaught card of a refused module"
    raise FlowError(msg)


def send_message(flow: Flow, entries: list[dict[str, Any]], text: str) -> str:
    """Queue the model's answers, type ``text`` in the app and Send."""
    script.write(queue(flow), entries)
    flow.screen("/session")
    since = flow.rids()
    flow.type_into(COMPOSER, text)
    flow.tap("Send")
    return flow.request("message", since)


def shown(flow: Flow, sid: str) -> list[str]:
    """The texts of the session's tutor bubbles, as the app renders them."""
    msgs = flow.db.node(f"sessions/{sid}/msgs")
    return [
        str(m.get("text")) for _, m in sorted(msgs.items()) if m.get("role") == "tutor"
    ]


def verify(
    flow: Flow, state: State, want: str, drafts: list[str], outcome: str
) -> None:
    """The last bubble is ``want``, no draft shows, the card stays untaught.

    The screenshot is named after ``state["shot"]`` (the phase).
    """
    sid, subject, card = str(state["sid"]), str(state["subject"]), str(state["card"])
    bubbles = shown(flow, sid)
    flow.step(f"the last tutor bubble is {want!r}")
    flow.note(f"tutor bubbles: {[s[:80] for s in bubbles]}")
    if not bubbles or bubbles[-1] != want:
        msg = f"last bubble {bubbles[-1:]!r}, want {want!r}"
        raise FlowError(msg)
    if hits := [d for d in drafts if any(d in s for s in bubbles)]:
        msg = f"a refused draft reached the page: {hits}"
        raise FlowError(msg)
    flow.step(f"{card} stays untaught; the transcript logs outcome {outcome}")
    if card in taught(flow, subject) or flow.db.node(f"sessions/{sid}/meta").get(
        "card_done"
    ):
        msg = f"{card} was marked done"
        raise FlowError(msg)
    logged = [
        e for e in _events(flow.args.data, sid) if e.get("type") == done_refusal.EVENT
    ]
    flow.note(f"card_done_rewrite events: {logged[-1:]}")
    if not logged or logged[-1]["outcome"] != outcome:
        msg = f"want a {outcome} card_done_rewrite, got {logged[-1:]}"
        raise FlowError(msg)
    if theory_rows(flow) != state["theory_rows"]:
        msg = "a theory-done row was minted"
        raise FlowError(msg)
    flow.screen("/session")
    flow.expect("Send", timeout=30)
    time.sleep(2)
    flow.shot(str(state["shot"]))


def front(flow: Flow, subject: str, card: str) -> str:
    """The front of ``card`` (what the learner reads, never the id)."""
    return Context(flow.args.data).subjects.cards(subject)[card].front


def ask_done(flow: Flow, entries: list[dict[str, Any]]) -> None:
    """The learner asks to finish; the queued model answers; the reply is ok."""
    rid = send_message(flow, entries, "I get it, mark this card done")
    if not _await(flow, rid, 40).get("ok"):
        msg = "the message was refused"
        raise FlowError(msg)


def prompted(flow: Flow, *wanted: str, banned: str = "") -> None:
    """The rewrite prompt the engine sent holds ``wanted``, never ``banned``."""
    lines = script.prompts(queue(flow)).read_text(encoding="utf-8").splitlines()
    asked = str(json.loads(lines[-1])["prompt"])
    flow.step(f"the rewrite prompt names {wanted}")
    flow.note(f"prompt: {asked[:260]}")
    if any(w not in asked for w in wanted) or (banned and banned in asked):
        msg = f"rewrite prompt lacks {wanted} or holds {banned!r}: {asked[:300]}"
        raise FlowError(msg)
