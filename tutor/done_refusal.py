# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A refused ``card_done`` never reaches the learner as "this card is done".

The done-gate (``phase_gate.blockers``) can refuse the tutor's ``card_done``:
a required card is not taught, or C3 refuses the card's module. The model's
draft then still says the card is finished. :func:`settle` runs right after
the model answers, before media and the clock stamp: it asks the live
session once more for a reply that names what blocks the card, keeps the card
open and offers the switch. That rewrite replaces the whole draft. If the
rewrite fails or claims the card done again, a fixed bubble is shown instead:
:data:`LOCK` plus the blocking card's front, or the module's plan title (both
deck content, never an id). The draft lives only in a ``card_done_rewrite``
transcript event, never in the page messages or the resume primer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import phase_gate

if TYPE_CHECKING:
    from tutor.cards import Card
    from tutor.conversation import Conversation
    from tutor.curriculum.source import CardSource
    from tutor.models import TutorTurn
    from tutor.session import TutorSession
    from tutor.store import Store

_logger = logging.getLogger(__name__)

LOCK: Final = "\N{LOCK}"
EVENT: Final = "card_done_rewrite"


@dataclass(frozen=True)
class Live:
    """The live turn's collaborators."""

    src: CardSource
    card: Card
    conv: Conversation
    store: Store


@dataclass(frozen=True)
class Settled:
    """The turn to show, its trace, and what blocked the draft's ``card_done``."""

    turn: TutorTurn
    trace: list[dict[str, str]] = field(default_factory=list)
    need: list[str] = field(default_factory=list)  # empty: nothing was refused


def wants_done(turn: TutorTurn, conv: Conversation, *, tap: bool) -> bool:
    """Whether ``turn`` ends its card: ``card_done``, not a follow-up, no tap.

    ``picked.refuse`` takes ``card_done`` out of every tapped reply, so a tap
    never ends a card (``cardflow._apply`` asks the same).
    """
    return turn.card_done and not conv.follow_up and not tap


def _fronts(src: CardSource, need: list[str]) -> list[str]:
    """The fronts of the required cards in ``need`` the deck still holds."""
    fronts = {c.id: c.front for c in src.cards()}
    return [fronts[n] for n in need if n in fronts]


def names(src: CardSource, card: Card, need: list[str]) -> list[str]:
    """What blocks ``card``, as the learner reads it.

    Required cards by their fronts; a C3 module refusal (or an id the deck no
    longer holds) by the card's module title, the plan's own.
    """
    return _fronts(src, need) or [card.topic.title]


def fallback_text(blocking: list[str]) -> str:
    """The fixed bubble: the lock glyph and what blocks the card."""
    return f"{LOCK} {', '.join(blocking)}"


def rewrite_prompt(blocking: list[str], *, module: bool) -> str:
    """Ask the model for the reply to show instead of its refused draft.

    ``module``: C3 closed the card's module (``blocking`` is its title), else
    ``blocking`` holds the fronts of required cards not taught yet.
    """
    shown = "; ".join(f'"{name}"' for name in blocking)
    why = (
        f"its module {shown} is closed for now. Say {shown} stays closed for "
        "now, and offer to switch to a card that is open."
        if module
        else f"it builds on {shown}, which the learner has not been taught. "
        f"Say this card stays open until {shown} is taught, name it exactly "
        "as quoted, and offer to switch to it now."
    )
    return (
        "Engine note: your card_done was refused. This card cannot be finished "
        f"yet: {why} Your last reply was NOT shown to the learner; write the "
        "reply to show instead. Never say this card is done or passed. Set "
        "card_done false. Repeat your check_result and low_effort for the "
        "learner's last answer unchanged."
    )


def _fallback(draft: TutorTurn, blocking: list[str]) -> TutorTurn:
    """The draft's grade with nothing of its text: :func:`fallback_text`."""
    return replace(
        draft,
        message=fallback_text(blocking),
        questions=(),
        choices=(),
        check=None,
        images=(),
        diagram=None,
        card_edits=(),
        card_done=False,
    )


def _log(live: Live, draft: str, blocking: list[str], outcome: str) -> None:
    event = {"type": EVENT, "draft": draft, "blockers": blocking, "outcome": outcome}
    live.store.log(live.conv.session_id, event)


async def settle(
    session: TutorSession, live: Live, prompt: str, *, tap: bool
) -> Settled:
    """Ask ``prompt``; the turn the learner sees (a refused done: rewritten).

    A subject whose profile draws no diagrams gets none (schemdraw draws
    circuits only).
    """
    turn, reply = await session.ask(prompt)
    if not live.src.profile.diagrams:
        turn = replace(turn, diagram=None)
    src, card = live.src, live.card
    wanted = wants_done(turn, live.conv, tap=tap)
    need = phase_gate.blockers(src, card) if wanted else []
    if not need:
        return Settled(turn, reply.trace)
    blocking = names(src, card, need)
    module = not _fronts(src, need)
    try:
        rewritten, again = await session.ask(rewrite_prompt(blocking, module=module))
    except (RuntimeError, TimeoutError, OSError) as err:  # SessionError, outages
        _logger.warning("card_done rewrite failed: %s; lock shown", err)
        rewritten = None
    if rewritten is None or rewritten.card_done:
        _log(live, turn.message, blocking, "fallback")
        return Settled(_fallback(turn, blocking), [], need)
    _log(live, turn.message, blocking, "rewritten")
    return Settled(rewritten, again.trace, need)


def hide_late(live: Live, message: dict[str, Any], need: list[str]) -> None:
    """A refusal only ``_apply`` saw (C3 moved during media): the lock bubble."""
    blocking = names(live.src, live.card, need)
    _log(live, str(message["text"]), blocking, "late")
    message |= {
        "text": fallback_text(blocking),
        "questions": [],
        "choices": [],
        "check": None,
    }


def final_need(
    live: Live,
    settled: Settled,
    logged: dict[str, Any],
    message: dict[str, Any],
    *,
    tap: bool,
) -> list[str]:
    """What refuses the settled turn's ``card_done`` now (empty: nothing).

    :func:`settle`'s own refusal, else the gate asked again: C3 may have
    closed the module while media ran. Such a late refusal hides the draft
    behind the lock bubble too (:func:`hide_late`) and drops its check.
    """
    if settled.need:
        return settled.need
    if not wants_done(settled.turn, live.conv, tap=tap):
        return []
    need = phase_gate.blockers(live.src, live.card)
    if need:
        hide_late(live, message, need)
        logged["check"] = None
    return need
