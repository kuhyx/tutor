# Tutor contract: struggling cards (v1)

Extends `DOCS-contract-curriculum.md` (§3 card, §4 fold, §6 cap) and
`DOCS-relay.md` (`session_start`). Change this file first, then code.

## 1. Card fields
- `mnemonic` (optional string): a memory aid the Review screen shows under
  `back`. NOT excerpt-checked (it states no fact of its own); <= 40 words,
  one line. Written by the tutor's `card_edits` op `mnemonic`
  (`{"op":"mnemonic","card":cid,"text":"..."}`, empty text clears it) or the
  Editor; setting or clearing it bumps `rev` like any `card_edit`.
- `split_of` (optional card id): set on a child of a split, never edited.

## 2. Split (`card_edits` op `split`)
`{"op":"split","card":cid,"into":[2..4 card drafts, each like an "add"]}`.
Atomic: every child passes the same rules and excerpt check as `add`, else
nothing changes and the whole edit is refused. Then the original is
`suspended:true` (never deleted), each child gets a NEW id (never a reused or
suspended one), `origin:"edited"`, `split_of` = the original id, the
original's `module` and `requires`, and orders right after it. Children start
untaught; teaching one is exempt from the daily new cap. The Editor's undo
reverts the whole split in one step (children suspended, original live).

## 3. Fold step 7: struggle
`struggle(c)` = the length of the trailing run of `r == 1` in c's reviews
kept by fold steps 2 and 6 since its last `taught`, counting only reviews
whose `rev == card.rev` (drill picks included). A kept `r >= 2` at the
current rev ends the run (0). So an edit (rev bump), a split (original
suspended) or a re-teach (`taught`) resets it; untaught: 0. Identical in
Python and Dart; pinned in `contract/fsrs_vectors.json` as
`expect.<c>.struggle`.

## 4. The offer (client, stateless)
Right after a rating that leaves `struggle(c) >= 3 && struggle(c) % 3 == 0`,
Review shows a dismissable "Struggling with this card?" sheet. It never
blocks the queue; dismissing records nothing, so it returns after 3 more
Again ratings. "Get help" sends `session_start` with `card` = c and
`struggle: true`; greyed out "PC offline" while the worker is absent.

## 5. Struggle session (`session_start` `struggle: true`)
Needs `card`, a taught card (else `unknown_card` / `locked` as usual). A fresh
session on that card in struggle mode: the tutor prompt gets the card, its
`struggle(c)` and its last 10 reviews (`r`, `at`). The tutor first finds what
keeps failing, then offers a mnemonic, a rewrite (`edit`), a split or a
re-teach, and the learner picks in the chat. Exempt from the new cap (a
re-teach). Pays active minutes like any session. Ends like any session:
`card_done` writes `taught`, which resets the streak.
