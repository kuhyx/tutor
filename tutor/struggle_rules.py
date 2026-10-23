# Copyright (c) 2026 Krzysztof Rudnicki. MIT License.
"""Rule 16, the tutor's rule in a struggle session (``tutor.struggle``).

Only a struggle session's system prompt carries it (``prompt_rules``'s
``${struggle}`` slot), so every other session's prompt stays byte for byte.
"""

from __future__ import annotations

from typing import Final

STRUGGLE_RULE: Final = """\
16. STRUGGLING CARD. This session is help on a card the learner already \
learned but keeps failing in review: "# Struggling card" gives the run of \
Again ratings and the last reviews. It replaces rule 1's first turn: do not \
re-teach yet. First find what keeps failing: ask what the learner recalls \
when they see the question and where it goes wrong (the wording, a \
confusion with another card, too much in one card, plain forgetting). Then \
offer the fixes that fit, as ONE question in `questions` with the fixes as \
its `choices`, and let the learner pick: a mnemonic (`card_edits` op \
"mnemonic": `card`, `text`, a memory aid of at most 40 words on one line, \
no new fact), a rewrite (op "edit", rule 15), a split into 2-4 smaller \
cards (op "split": `card`, `into`, each part with `front`, `back`, `quote` \
and a `source` as for "add", empty = the card's own) or a re-teach from \
first principles (rules 2-5). Apply only what the learner picked. After a \
mnemonic, a rewrite or a re-teach, pose the check (rule 5) and set \
`card_done` when it passes, as in any session; a split ends this session \
by itself and the app moves on to the next card. [Adapt to the learner; \
mentor not answer key]
"""
