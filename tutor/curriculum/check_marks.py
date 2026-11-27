# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Cards taught without Claude, waiting for its check (``README.md`` "Fallback").

Read mode and a free-model chat mark each card they cover ``unchecked``
(fold step 11). The next Claude session of the subject opens on those cards
first, plan order, one session each (spec Q10), before any new card; the
module gate holds while one is left (:func:`tutor.curriculum.pick.gate`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tutor import backend_mode
from tutor.curriculum.pick import teachable
from tutor.curriculum.rules import counted

if TYPE_CHECKING:
    from tutor.curriculum.fold import Fold
    from tutor.curriculum.rules import View


def first_unchecked(view: View, fold: Fold, skip: str = "") -> str | None:
    """The subject's first unchecked card a session may open now, or None.

    Only modules a session may teach in (open, unlocked, not refused by C3,
    ``view.only`` if set); never ``skip`` (Next card leaves it). None in a
    free-model session: only Claude checks (``backend_mode``).
    """
    if backend_mode.free():
        return None
    for module in teachable(view, fold):
        for cid, state in counted(view, module.id, fold):
            if state.unchecked and cid != skip:
                return cid
    return None
