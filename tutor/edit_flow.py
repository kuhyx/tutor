# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's ``card_edits``, applied right after the turn that asks for them.

The tutor edits on the learner's criticism or on its own initiative (prompt
rule 15). Each edit goes to the data-dir subject (``curriculum.card_ops``:
edit / add / remove; an unmigrated subject on the repo deck is refused) in a
worker thread, guarded by the subject store's lock, so it cannot clobber or
be clobbered by a card generation's commit. Not on the relay's build lane:
generation holds that lock for minutes, and the edit must land with the
turn. Applied edits become ``notices`` lines on the turn's page message
("Card removed: <front>"), which the transcript and the relay projection
keep; refused ones go to the tutor in the next engine note. Removing the
live card ends the session (``next_card`` + ``stop``, as Next card does) and
opens the next card, whose first message carries the notice; with no card
left the session stops. A rewrite of the live card reaches the model from
the card's next session (the prompt is per session). Undo: the Editor.
``Engine`` mixes this in.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any, Final

from tutor.curriculum import card_ops
from tutor.curriculum.errors import EDIT_REFUSED, RequestError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from tutor import cards as cards_mod
    from tutor.card_requests import CardEdit
    from tutor.conversation import Conversation
    from tutor.curriculum.context import Context
    from tutor.curriculum.source import CardSource
    from tutor.models import TutorTurn
    from tutor.store import Store

_REFUSED: Final = (
    "card_edits refused (nothing changed; tell the learner briefly and do "
    "not retry the same edit): "
)
_logger = logging.getLogger(__name__)


@dataclass
class Applied:
    """What a turn's edits did."""

    notices: list[str] = field(default_factory=list)
    refusals: list[str] = field(default_factory=list)
    removed_live: str = ""  # its notice, when the live card was removed


def _one(ctx: Context, subject: str, live: str, edit: CardEdit) -> tuple[str, bool]:
    """Apply ``edit``; returns its notice and whether it removed the live card."""
    if ctx.subjects.meta(subject) is None:
        msg = f"{subject} still runs on the repo deck, which only kuhy edits by hand"
        raise RequestError(EDIT_REFUSED, msg)
    cid = edit.card or live
    if edit.op == "remove":
        rec = card_ops.remove(ctx, subject, cid)
        return f"Card removed: {rec.front}", cid == live
    if edit.op == "add":
        topic = edit.topic or getattr(
            ctx.subjects.cards(subject).get(live), "module", ""
        )
        draft = card_ops.Draft(topic, edit.front, edit.back, edit.source)
        _, rec = card_ops.add(ctx, subject, draft)
        return f"Card added: {rec.front}", False
    rec = card_ops.rewrite(ctx, subject, cid, front=edit.front, back=edit.back)
    return f"Card updated: {rec.front}", False


def apply_edits(
    ctx: Context, subject: str, live: str, edits: tuple[CardEdit, ...]
) -> Applied:
    """Every edit in order; a refused one changes nothing and is reported."""
    done = Applied()
    for edit in edits:
        target = edit.card or (edit.topic if edit.op == "add" else live)
        try:
            notice, live_gone = _one(ctx, subject, live, edit)
        except (ValueError, OSError, LookupError) as err:  # RequestError: a refusal
            why = getattr(err, "message", repr(err))
            _logger.warning("card edit %s %s refused: %s", edit.op, target, why)
            done.refusals.append(f"{edit.op} {target or live}: {why}")
            continue
        done.notices.append(notice)
        if live_gone:
            done.removed_live = notice
    return done


class EditFlow:
    """``_edit_cards`` after each model turn, ``_leave_removed`` after a reply."""

    if TYPE_CHECKING:
        store: Store
        source: CardSource
        card: cards_mod.Card | None
        _conv: Conversation | None
        _open: Callable[..., Awaitable[None]]
        close: Callable[[], Awaitable[None]]

        @property
        def ctx(self) -> Context:
            """The curriculum context (``CardFlow``)."""

    async def _edit_cards(
        self,
        conv: Conversation,
        turn: TutorTurn,
        message: dict[str, Any],
        carried: Sequence[str] = (),
    ) -> str:
        """Apply the turn's edits: notices on ``message``, refusals in the notes.

        ``carried``: notices from the session this one replaced. Returns the
        notice of the live card's removal ("" when it stays).
        """
        notices, gone = list(carried), ""
        if turn.card_edits:
            args = (self.ctx, self.source.subject, conv.card_id, turn.card_edits)
            done = await asyncio.to_thread(apply_edits, *args)
            notices += done.notices
            if done.refusals:
                conv.notes.append(_REFUSED + "; ".join(done.refusals))
            gone = done.removed_live
        if notices:
            message["notices"] = notices
        return gone

    async def _leave_removed(self, conv: Conversation, gone: str, device: str) -> None:
        """The live card was removed (``gone``): open the next card, or stop."""
        if not gone:
            return
        sid = conv.session_id
        try:
            nxt = self.source.pick(None, skip=conv.card_id)
        except ValueError as err:
            _logger.warning("removed the live card; no next card: %s", err)
            self.store.log(sid, {"type": "stop"})
            await self.close()
            self._conv, self.card = None, None
            return
        self.store.log(sid, {"type": "next_card", "card": nxt.id})
        self.store.log(sid, {"type": "stop"})
        await self._open(self.source, nxt.id, device, [gone])
