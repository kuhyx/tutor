# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Which model does which job (kuhy, 2026-11-21).

Drafting cards is a one-off cost per card, so it gets the best model:
``DRAFT`` (Fable 5.2 at ``xhigh``) writes new modules' cards, the backfill
(``redraft``), the rule judge and the interrogation paths. Everything the
learner repeats runs on ``REPEAT`` (Sonnet at ``high``): the live tutor, a
requested regeneration, plans and profiles. There is no fallback: a draft
that Fable cannot write fails (``model_failed`` / ``claude_unavailable``)
and is retried, never written by a weaker model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from tutor.session import MODEL, TURN_TIMEOUT

if TYPE_CHECKING:
    from tutor.session import Effort


@dataclass(frozen=True)
class Tier:
    """A model, its effort and how long one turn may take (seconds)."""

    name: str
    model: str
    effort: Effort
    timeout: float


DRAFT: Final = Tier("draft", "claude-fable-5-2", "xhigh", 1800.0)
REPEAT: Final = Tier("repeat", MODEL, "high", TURN_TIMEOUT)
