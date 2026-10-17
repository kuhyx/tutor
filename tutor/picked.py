# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""A tapped answer to the comprehension check never passes it on its own.

The app sends an answer box that a choice filled, unedited, as
``A: <choice> (picked option)`` (``app/lib/session/answers.dart``). While a
check is open, any such line makes the reply a tap: the model is told so
before it answers (:func:`note`), and whatever it returns, :func:`refuse`
takes the pass, the mastery and ``card_done`` back out of the turn and makes
sure the learner is asked one short why, which must be typed (no choices).
Fail-safe: a tap on any box counts, since a check turn asks nothing else.
Since 2026-10-17 a check is typed (no choices), so only a check logged
before then, resumed with its old chips, can still be tapped.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from tutor.conversation import CheckState

MARKER: Final = "(picked option)"
_TAPPED: Final = re.compile(rf"^A: .*{re.escape(MARKER)}[ \t]*$", re.MULTILINE)
# The code-posed why: "right" only when the model did grade the tap a pass.
WHY: Final = "Why is that the right answer? Say it in one sentence."
WHY_UNGRADED: Final = "Why that answer? Say it in one sentence."
NOTE: Final = (
    "check_answer: TAPPED - the learner answered the open check by tapping one "
    "of its choices. A tap alone never passes (rule 14). If it is wrong, grade "
    "it not yet as usual. If it is right, leave check_result null, say it is "
    "right, and pose ONE short why as `check` (same concept, answerable in one "
    "sentence, `choices` []); grade that why next turn"
)
REFUSED: Final = (
    "Your last check_result passed a TAPPED choice. The app does not count a "
    "tap: the check is still open and the learner was asked why; grade the why"
)


def tapped(text: str) -> bool:
    """Whether a learner reply carries an answer filled by a tapped choice."""
    return bool(_TAPPED.search(text))


def note(*, tap: bool) -> list[str]:
    """The engine-note line for this reply (none when nothing was tapped)."""
    return [NOTE] if tap else []


def refuse(logged: dict[str, Any], message: dict[str, Any], check: CheckState) -> bool:
    """Strip a tapped reply's turn of everything a tap must not earn.

    ``logged`` is the transcript's copy of the turn, ``message`` the page's;
    both are edited, so replay rebuilds exactly this. A "not yet" stands (a
    wrong tap is a wrong answer). Otherwise the check stays open with a why
    posed: the model's own why, else :data:`WHY` (or, with no grade at all,
    :data:`WHY_UNGRADED`: nothing has judged the tap right). Returns
    ``True`` when the model's pass was taken back.
    """
    if logged.get("concepts_mastered"):
        logged["concepts_refused"] = logged["concepts_mastered"]
        logged["concepts_mastered"] = []
    if logged.get("card_done"):
        logged["card_done"], logged["card_done_tapped"] = False, True
    result = logged.get("check_result")
    if result is not None and not result.get("passed"):
        return False
    passed = result is not None
    if passed:
        logged["check_result_refused"] = result
        logged["check_result"] = message["check_result"] = None
    why = WHY if passed else WHY_UNGRADED
    posed = logged.get("check") or {"question": why, "concept": check.concept}
    logged["check"] = message["check"] = {**posed, "choices": []}
    return passed
