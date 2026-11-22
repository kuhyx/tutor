# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C3 at the engine's doors: a live, resumed or finished card of a refused module.

``SubjectSource.pick`` and ``mark`` refuse a module ``theory_phase`` does not
list; these helpers carry the same rule to the paths that never pick: a
reply on the live card, a resume, a follow-up and the tutor's own
``card_done``. Every refusal reuses an existing state (the pick's
``no_card_left``, a resume that "cannot be continued", a refused
``card_done``), so no new text reaches the learner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import continuing, gating, resume
from tutor.curriculum import theory_phase
from tutor.curriculum.source import SubjectSource

if TYPE_CHECKING:
    from pathlib import Path

    from tutor.cards import Card
    from tutor.curriculum.source import CardSource


def refuses(src: CardSource, card_id: str) -> bool:
    """Whether ``card_id``'s module is one C3 does not let the tutor teach now."""
    if not isinstance(src, SubjectSource) or src.subject not in theory_phase.GATED:
        return False
    rec = src.ctx.subjects.cards(src.subject).get(card_id)
    return rec is not None and bool(theory_phase.refused(src.subject, [rec.module]))


def refuse_live(src: CardSource, card_id: str) -> None:
    """Raise the pick's own refusal (``no_card_left``) for a refused live card."""
    if refuses(src, card_id):
        src.pick(card_id)  # pick.pick: a refused module's card always raises


def blockers(src: CardSource, card: Card) -> list[str]:
    """What keeps the tutor's ``card_done`` from marking ``card`` taught.

    The requires not done yet (``gating``), else the card's module when C3
    refuses it (the phase moved while the model was answering).
    """
    need = gating.missing(card, src.done())
    return need or ([card.topic.stem] if refuses(src, card.id) else [])


def open_session(sessions_dir: Path, src: CardSource) -> Path | None:
    """``continuing.open_session``, but never one on a refused module's card."""
    found = continuing.open_session(sessions_dir, src.subject, src.done())
    state = resume.replay(found) if found else None
    if state is not None and refuses(src, state.conversation.card_id):
        return None
    return found
