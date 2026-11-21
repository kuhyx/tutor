# Tutor contract: model tiers, card rules, interrogation paths, redraft

PC-only: nothing here is published to the phone. Part of
`DOCS-contract-curriculum.md` (§3, the generation pipeline).

- The seven card rules (`curriculum/quality.py`): one question per card; no
  unguessable name or number; an abbreviation card asks only for the
  expansion and carries a `mnemonic`; one term per card; a maths card answers
  with the formula; nothing subjective or hedged; a card the learner found
  hard carries a `mnemonic`. Code checks, then a judge call; a failing card
  is repaired by the model at most 3 times, then dropped
  (`curriculum/vet.py`).
- Model tiers (`tutor/tiers.py`, PC-only): the draft tier (`claude-fable-5-2`,
  effort `xhigh`) writes a new module's cards (steps 1-7), drafts ahead,
  judges the seven rules, writes interrogation paths and runs the redraft;
  the repeat tier (`claude-sonnet-5-5`, effort `high`) serves the live tutor,
  plans, profiles, `card_edit`, card splits and a requested regeneration
  (`python -m tutor regenerate`; the module carries `repeat:true` until it
  is drafted). No fallback between tiers: a draft-tier failure is `failed`
  (`model_failed` / `claude_unavailable`), retried by `plan_approve`.
- Interrogation paths (PC-only, never published): `subjects/<id>/paths.json`,
  card id -> `{rev, path}`; `path` = `opening`, `probes`, `misconception`,
  `correction`, `hints`, `tell`, `pass_criterion`, `typed_follow_up`. Written
  by the draft tier per card revision; a path of another `rev` is stale and
  ignored, and the worker rewrites it in the background
  (`relay/redraft_task.py`). The tutor reads it as suggestions before its
  first question and may leave it whenever the learner does.
- Redraft (`python -m tutor redraft start|status|drain|report`, PC-only):
  every module with cards is drafted again by the draft tier from the pages
  its cards cite plus a fresh source search. A new card the model matches to
  an old one takes the old id with `rev`+1 (taught state and schedule carry
  over, flags clear); an old card with no match is `suspended:true`
  (`tutor.redraft` = ms); over 12 cards the model cuts the module: the first
  piece keeps the module id, the others get new ids right after it, each
  requires the one before, dependents require the last. A module with no
  passing card keeps its old cards. State in `$TUTOR_DATA/redraft/`; the
  live queue is drained by the server, which waits while a reply is in
  flight.
