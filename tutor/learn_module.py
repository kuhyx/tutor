# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""C4: a session on one module (``session_start`` with ``module``).

The lock's learn button opens ``/learn/<subject>/<module>``; the app sends
this. A live or open session whose card is an untaught card of the module
is reused (never a second session on it). Otherwise the module's next
untaught card is picked by ``pick.pick`` with ``View.only``, so a module C3
refuses, one with no cards yet, an unknown one and a finished one all get
the pick's own ``no_card_left``: C3 stays the one place that refuses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor import resume
from tutor.curriculum import phase_gate
from tutor.curriculum.errors import BAD_REQUEST, NO_CARD_LEFT, RequestError
from tutor.curriculum.source import SubjectSource, source_for

if TYPE_CHECKING:
    from tutor.engine import Engine


def _untaught_in(src: SubjectSource, card_id: str, module: str) -> bool:
    rec = src.ctx.subjects.cards(src.subject).get(card_id)
    return rec is not None and rec.module == module and card_id not in src.done()


async def _reuse(engine: Engine, src: SubjectSource, module: str) -> bool:
    """Make the live or open session on ``module`` live; ``False``: none."""
    live = engine.card if engine.source.subject == src.subject else None
    if engine.session_id and live is not None:
        return _untaught_in(src, live.id, module)
    found = phase_gate.open_session(engine.store.root / "sessions", src)
    state = resume.replay(found) if found else None
    if found is None or state is None:
        return False
    if not _untaught_in(src, state.conversation.card_id, module):
        return False
    await engine.resume_session(found)
    return True


async def start(engine: Engine, body: dict[str, Any], device: str) -> dict[str, Any]:
    """Teach ``body["module"]`` of ``body["subject"]``; returns the session."""
    subject, module = body["subject"], str(body["module"])
    if subject is None or body["card"] is not None:
        msg = "a module start names its subject and no card"
        raise RequestError(BAD_REQUEST, msg)
    src = source_for(engine.store, engine.ctx, subject)
    if not isinstance(src, SubjectSource):
        msg = f"{subject} has no modules"
        raise RequestError(NO_CARD_LEFT, msg)
    if not await _reuse(engine, src, module):
        card = src.pick(None, module=module)  # raises the pick's refusals
        await engine.start(card.id, subject=subject, device=device)
    return {"session": engine.session_id}
