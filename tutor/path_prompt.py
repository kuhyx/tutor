# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The interrogation path as the tutor reads it (``curriculum.paths``).

A section of the system prompt, never shown to the learner. The wording
makes it advice: kuhy wants the tutor to read it before the first question
and keep it in mind, and to react to what the learner actually does when
they leave it (2026-11-21). ``typed_follow_up: false`` answers his
"redundant" feedback (2026-10-15): after a correct pick the tutor asked him
to type the same answer again.
"""

from __future__ import annotations

from typing import Any, Final

HEAD: Final = (
    "# Suggested interrogation path\n"
    "A stronger model planned this card's questioning in advance. Read it "
    "before your first question and keep it in mind. These are SUGGESTIONS, "
    "not a script: you do not have to follow them, and the rules above win "
    "over them. When the learner deviates (knows more, misunderstands "
    "something else, asks their own question, answers unexpectedly), react "
    "to what they actually wrote instead of returning to the next step "
    "here. Never read the path out or mention that it exists.\n"
)
NO_TYPED: Final = (
    "typed follow-up after a correct pick: NOT needed. When the learner "
    "taps the right option, accept it and move on to the next step; do not "
    "ask them to type the same answer or a why for it (that is redundant "
    "on this card). The final check stays as rule 5 says."
)
TYPED: Final = (
    "typed follow-up after a correct pick: useful here. A tap can be a "
    "guess; one short typed why shows the understanding."
)


def _listed(label: str, items: object) -> str:
    rows = [str(i) for i in items] if isinstance(items, list) else []
    return f"{label}:\n" + "".join(f"- {r}\n" for r in rows) if rows else ""


def section(path: dict[str, Any] | None) -> str:
    """The prompt section for ``path`` ("" when the card has none yet)."""
    if not path:
        return ""
    wrong, fix = path.get("misconception"), path.get("correction")
    return (
        f"{HEAD}opening question: {path.get('opening', '')}\n"
        f"{_listed('probes (tell knowing from guessing)', path.get('probes'))}"
        + (f"likely misconception: {wrong}\ncorrection: {fix}\n" if wrong else "")
        + _listed("hint ladder (weakest first)", path.get("hints"))
        + _listed("state these, never ask the learner to guess", path.get("tell"))
        + f"pass criterion: {path.get('pass_criterion', '')}\n"
        + (TYPED if path.get("typed_follow_up") is not False else NO_TYPED)
        + "\n\n"
    )
