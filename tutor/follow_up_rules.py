# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""The follow-up wording the engine adds to a turn after the card is done."""

from __future__ import annotations

from typing import Final

# The engine-note line of a follow-up turn (``prompt.engine_note``): the card
# is done and the learner asks on, at card end or in a session reopened from
# History. A note, not a numbered rule: the model process at card end is
# already running, so its system prompt cannot change (kuhy, 2026-10-20).
FOLLOW_UP: Final = (
    "follow_up: yes - the target card is DONE and stays done. The learner is "
    "asking follow-up questions about it or around it. Answer whatever they "
    "ask in the way that teaches best: explain, ask them to reason, pose a "
    "check if it helps. General knowledge is welcome here: you are not "
    "limited to the card's source or excerpt; research (rule 9) when you "
    "are unsure of a fact. Rules 1 (diagnose first), 3's \"stop teaching "
    "once the card's answer is given\" and 5's checks on the target card do "
    "not apply. Leave `card_done` false: the card is already done and "
    "nothing you do undoes it. The app keeps offering Next card / Stop here."
)
