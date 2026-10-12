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
    """The newest unstopped session of ``subject`` whose card is still open.

    Open: its card is untaught, or was taught in that very session (it then
    offers Next card / Stop here). A session whose card was taught elsewhere
    since is stale and skipped. Transcripts from before subjects existed
    belong to ``automation``.
    """
    for path in sorted(sessions_dir.glob("*.jsonl"), reverse=True):
        if not history.SESSION_ID.fullmatch(path.stem):
            continue
        if (transcript_subject(path) or DEFAULT_SUBJECT) != subject:
            continue
        state = resume.replay(path)
        if state is None or state.conversation.stopped:
            continue
        taught = done.get(state.conversation.card_id)
        if taught is None or taught.get("session") == path.stem:
            return path
    return None
