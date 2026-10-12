# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Which past session "Continue" picks up for a subject.

One live session at a time, many subjects: starting a card of another
subject leaves the old session unstopped, and a restart resumes the newest
transcript of the day whatever its subject. So Continue on Home names the
subject the learner is in, and the worker looks for that subject's session
(kuhy, 2026-10-12: Continue in automation opened a car session).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tutor import history, resume
from tutor.curriculum.source import DEFAULT_SUBJECT, transcript_subject

if TYPE_CHECKING:
    from pathlib import Path


def open_session(
    sessions_dir: Path, subject: str, done: dict[str, dict[str, Any]]
) -> Path | None:
    """``subject``'s newest session, if it is still open; else ``None``.

    Open: not stopped, and its card untaught or taught in that very session
    (it then offers Next card / Stop here). Only the newest counts: once
    the learner stopped (or moved past) it, Continue means the next card,
    not an older abandoned session (live data held unstopped automation
    sessions from days before). Transcripts with nothing said yet are
    skipped; those from before subjects existed belong to ``automation``.
    """
    for path in sorted(sessions_dir.glob("*.jsonl"), reverse=True):
        if not history.SESSION_ID.fullmatch(path.stem):
            continue
        if (transcript_subject(path) or DEFAULT_SUBJECT) != subject:
            continue
        state = resume.replay(path)
        if state is None:
            continue
        taught = done.get(state.conversation.card_id)
        is_open = taught is None or taught.get("session") == path.stem
        return None if state.conversation.stopped or not is_open else path
    return None
