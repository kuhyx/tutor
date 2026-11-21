# Tutor contract: a card's code skeleton (v1)

Extends `DOCS-contract-curriculum.md` §3 (card). Change this file first,
then code.

- `code` (optional string): a code skeleton, for instance the TypeScript
  shape of the LeetCode pattern a card teaches. Review (phone and desktop)
  and the focus check-in show it as selectable monospace code under `back`,
  with no label; a card without it looks as before.
- Its newlines and indentation are kept. Only trailing whitespace is
  dropped. It is never excerpt-checked (it states no fact of its own).
- It counts against the 2000-byte card budget (`records.MAX_CARD_BYTES`);
  each newline costs 2 bytes once JSON-encoded. A drafted card over budget
  is refused by `vet` (repaired or dropped, listed in `dropped`); a
  `card_edit` over budget is `bad_request` and nothing is written.
- `card_edit`: an absent `code` keeps the card's, `""` clears it. A split
  card starts with none.
- Drafting writes one only when the learner's goal asks for code on the
  cards (at most 20 lines, in the language the goal names), else `""`.
- The tutor gets it in the target card as `skeleton:` and teaches from it.
- It reaches the phone in `subjects/{subj}/cards` like every card field;
  `paths.json` (PC-only) never holds it.
