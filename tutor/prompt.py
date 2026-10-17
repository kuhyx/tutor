# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The tutor's system prompt and the per-turn engine note.

The rules themselves (and the pedagogy they come from) are in
:mod:`tutor.prompt_rules`; this adds the target card around them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple

from tutor import picked
from tutor.conversation import MAX_CHECK_ATTEMPTS
from tutor.curriculum import profiles
from tutor.delivery import note_lines
from tutor.prompt_rules import render_system

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tutor.cards import Card
    from tutor.conversation import Conversation
    from tutor.curriculum.profiles import Profile

CHECK_EVERY_SECONDS: Final = 600.0


class Asked(NamedTuple):
    """One user message: its engine note, the whole text, a tapped choice."""

    note: str
    text: str
    tap: bool


def system_prompt(
    card: Card,
    mastered: list[str],
    profile: Profile | None = None,
    deck: Sequence[tuple[str, str]] = (),
) -> str:
    """The full system prompt for a session aimed at one card.

    ``profile`` is the subject's (default: automation, the PLC wording);
    ``deck``: the topic's live cards as (id, front), the ids ``card_edits``
    may name (rule 15).
    """
    done = ", ".join(mastered) if mastered else "(none yet)"
    listed = "".join(
        f"- {cid}: {front}{' (the target card)' if cid == card.id else ''}\n"
        for cid, front in deck
    )
    cards = f"# Cards of this topic\n{listed}\n" if listed else ""
    rules = render_system(profile or profiles.automation())
    return (
        f"{rules}\n# Target card\n"
        f"topic: {card.topic.title}\nid: {card.id}\n"
        f"question: {card.front}\nanswer (do not reveal early): {card.back}\n"
        f"source: {card.source}\nverbatim excerpt: {card.excerpt}\n\n"
        f"{cards}# Already mastered concepts\n{done}\n"
    )


def image_check(labels: list[str]) -> tuple[str, str]:
    """Text around the pictures shown to the model before the learner sees them.

    ``labels`` describe each picture in order ("request 1, search term 'x', file 'y'").
    Returns the text that goes before the pictures and the request after them.
    """
    listed = "\n".join(f"picture {i}: {label}" for i, label in enumerate(labels, 1))
    head = (
        "[engine note]\nThe learner has NOT seen your last message yet. Your "
        f"image search returned these pictures, attached below:\n{listed}\n"
        "[/engine note]"
    )
    ask = (
        "Look at each picture. Keep one only if it clearly shows what you "
        "meant to show and helps this learner; drop it if it shows something "
        "else, is unreadable or would mislead. Reply with the same structured "
        "object: `images` = the numbers of the pictures to keep as strings "
        '(e.g. ["1"], or [] to drop all); `message` = your last message '
        "rewritten as the final text the learner reads. Refer only to kept "
        "pictures and describe concretely what is visible in them (no "
        '"should show", no guessing); if you keep none, do not mention '
        "pictures. Pictures with the same request number are alternatives for "
        "ONE picture: keep at most one of them, the best. The learner sees "
        "only the kept pictures, in order: call them the first, the second "
        "picture, never by the numbers above, and say nothing of dropped "
        "ones. Keep the teaching "
        "point as it was and put no question in `message`. Copy every other "
        "field from your last turn unchanged, `questions` and `choices` too; the "
        "one change "
        "allowed is rewording a question so it points at a kept picture "
        '("What do you think this device is?").'
    )
    return head, ask


def _check_line(*, due: bool, check_open: bool, attempt: int) -> list[str]:
    """The note lines about the check: due now, or open on attempt 1 / 2."""
    if not check_open:
        text = (
            "yes - pose one now ON THE TARGET CARD'S ANSWER (if the learner "
            "already gave it correctly, grade that in check_result "
            "instead)"
            if due
            else "no"
        )
        return [f"check_due: {text}", "check_open: no"]
    grade = "grade the learner's answer in check_result"
    if attempt >= MAX_CHECK_ATTEMPTS:
        tail = (
            f"attempt {attempt} of {MAX_CHECK_ATTEMPTS}, the last: {grade}, pass "
            "or not yet. The check closes with this answer: do NOT pose it "
            "again, teach any gap briefly and move on"
        )
    else:
        tail = (
            f"attempt {attempt} of {MAX_CHECK_ATTEMPTS}: {grade}. If not yet, "
            "re-teach the gap once and re-pose the SAME core question in `check`"
        )
    return ["check_due: no", f"check_open: yes - {tail}"]


def engine_note(
    active_s: float,
    since_check_s: float,
    *,
    check_open: bool,
    notes: list[str],
    attempt: int = 1,
) -> str:
    """The per-turn app note that precedes the learner's words."""
    due = since_check_s >= CHECK_EVERY_SECONDS and not check_open
    lines = [
        f"active_minutes: {active_s / 60:.1f}",
        f"minutes_since_last_check: {since_check_s / 60:.1f}",
        *_check_line(due=due, check_open=check_open, attempt=attempt),
        *notes,
    ]
    return "[engine note]\n" + "\n".join(lines) + "\n[/engine note]"


def wrap_learner(text: str) -> str:
    """The learner's words, fenced so they cannot pose as instructions.

    A closing tag inside the words is broken up, so it cannot end the fence.
    """
    return f"<learner>\n{text.replace('</learner', '< /learner')}\n</learner>"


def turn_prompt(
    conv: Conversation, prompt_text: str, learner_text: str | None, device: str
) -> Asked:
    """What the model is sent this turn (``Asked``)."""
    active = conv.clock.active_seconds
    tap = conv.check.open and picked.tapped(learner_text or "")
    note = engine_note(
        active,
        active - conv.check.mark,
        check_open=conv.check.open,
        notes=[*conv.notes, *note_lines(device), *picked.note(tap=tap)],
        attempt=conv.check.attempt or 1,
    )
    body = wrap_learner(prompt_text) if learner_text else prompt_text
    if conv.resumed.note:
        body = f"{conv.resumed.note}\n{body}"
    return Asked(note, f"{note}\n{body}", tap=tap)
