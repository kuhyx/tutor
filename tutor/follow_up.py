# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Follow-up questions after a card is done (kuhy, 2026-10-20).

Two ways in. At card end the composer stays next to Next card / Stop here:
a message sent there is a follow-up turn. From History, a session whose card
was done there is reopened with ``follow_up_open``, logged in the SAME
transcript; replay then makes it live again (``Conversation.reopen``) and a
later ``stop`` ends it again.

In follow-up mode the learner and tutor events carry ``"follow_up": true``,
the engine note says so (``follow_up_rules.FOLLOW_UP``) and never asks for a
check, and the card never becomes "not done": the tutor's ``card_done`` is
ignored, a failed check changes nothing, and the session's ``card_done``
stays true (``Conversation.set_done``). Removing the live card ends the
session cleanly (``EditFlow._leave_removed``). Minutes count as in any
session: the clock and the credit rows continue the session's own numbering,
because the reopened session is rebuilt by replay, never started afresh.
``Engine`` mixes this in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from tutor import resume

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from tutor.cards import Card
    from tutor.conversation import Conversation
    from tutor.curriculum.source import CardSource
    from tutor.session import TutorSession
    from tutor.store import Store

REOPENED: Final = (
    "[app] This session had ended; the learner reopened it to ask follow-up "
    "questions, so you are a fresh process."
)


def enter(conv: Conversation) -> None:
    """A learner message on a done card starts follow-up mode (it then stays)."""
    if conv.card_done:
        conv.follow_up = True


def tag(conv: Conversation) -> dict[str, Any]:
    """The transcript tag of an event in follow-up mode (else nothing)."""
    return {"follow_up": True} if conv.follow_up else {}


class FollowUpFlow:
    """``follow_up_open``: reopen a finished session from History."""

    if TYPE_CHECKING:
        store: Store
        _conv: Conversation | None
        _lock: asyncio.Lock
        time: Callable[[], float]
        resume_path: Callable[[Path], bool]
        close: Callable[[], Awaitable[None]]
        state: Callable[[], dict[str, Any]]
        _resume_source: Callable[[Path | None], CardSource]
        _live: Callable[[], tuple[TutorSession, Conversation, Card]]

    async def follow_up_open(self, path: Path) -> dict[str, Any]:
        """Make the session in ``path`` live again for follow-up questions.

        Already live: nothing changes. Raises ``ValueError`` while another
        session is live (the learner stops it first, so a reopen never
        silently leaves one), when the card was not finished in that session
        (Repeat starts it again) or is gone from the deck.
        """
        async with self._lock:
            live = self._conv
            if live is not None and live.session_id == path.stem:
                return self.state()
            if live is not None:
                msg = (
                    f"session {live.session_id} is live: stop the current "
                    "session first, then ask the follow-up"
                )
                raise ValueError(msg)
            state = resume.replay(path)
            conv = state.conversation if state else None
            if conv is None or not conv.card_done:
                msg = "its card was not finished in that session; use Repeat"
                raise ValueError(msg)
            cards = self._resume_source(path).cards()
            if not any(c.id == conv.card_id for c in cards):
                msg = f"its card {conv.card_id} is gone from the deck"
                raise ValueError(msg)
            await self.close()
            self.store.log(path.stem, {"type": "follow_up_open", "t": self.time()})
            self.resume_path(path)
            conv = self._live()[1]
            conv.resumed.note = resume.primer(conv.messages, REOPENED)
        return self.state()
