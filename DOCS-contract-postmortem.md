# Contract: the unit post-mortem (leetcode-guard <-> tutor)

When a unit is finished, the tutor analyses how kuhy solved its problems,
fixes the unit's own cards, sends the unit back to THEORY for a re-pass, and
records lessons that every later card draft reads. Spec: todo part
4d34709b-0 (kuhy, 2026-11-23). Code: `tutor/postmortem/`.

## Files

| File | Writer | Signed | Read by |
|---|---|---|---|
| guard `unit_finish.json` (C6) | guard `_unit_finish.record_finishes` | row HMAC | `postmortem.watch` |
| guard `postmortem_dry_run.json` | guard `--postmortem-dry-run` | row HMAC | `postmortem.dry` |
| `postmortems/<subject>/<unit>.json` | `report.save` | doc HMAC | guard `/api/postmortems`, snapshot |
| `postmortems/<subject>/lessons.json` | `lessons.record` | doc HMAC | `draft_prompt` |
| `postmortems/revisions.json` (C7) | `report.record_revision` | row HMAC | guard `_theory_redone` |
| `postmortems/failed/<unit>-<rev>.json` | `watch._fail` | no | `watch.due` (stops the unit) |
| `postmortems/tasks/<name>.json` | `todo.queue` | no | `todo.flush` (todo MCP) |
| `postmortems/dry/<unit>.json` | `dry.work` | no | `dry.auto` (display only) |

Every signature is the fleet key (`earned_time.entry_signature`), so either
side verifies the other's rows. A forged or edited row is dropped; it can
never start a post-mortem or pay a credit.

### C6 row

```json
{"kind": "unit_finish", "entry_id": "finish:<unit>:<n>", "day": "YYYY-MM-DD",
 "detail": {"unit": "prefix-sums", "subject": "...", "modules": ["..."],
            "at": 1795400000.0, "solves": ["slug", "..."]}, "hmac": "..."}
```

The guard appends one when a unit the phase machine has moved past claims a
different set of solved problems than its last row. `solves` is every slug the
unit claims (`Curriculum.unit_index`, any difficulty) with a trusted ledger row.

### C7 row

```json
{"kind": "postmortem_rev", "entry_id": "pm:<subject>:<unit>:<rev>", "day": "...",
 "detail": {"unit": "...", "subject": "...", "modules": ["..."], "rev": 1,
            "at": 1795400000.0}, "hmac": "..."}
```

## When a post-mortem runs

The worker's `PostmortemWork` ticks once a minute (`TUTOR_POSTMORTEM_WORK=off`
stops it) and waits while a learner's reply is in flight. A unit is due when:

1. its latest verified C6 row claims at least 3 solves that no earlier revision
   of its report saw (`report.seen`), so a finish after the re-pass, which adds
   no solve, starts nothing;
2. no failed marker exists for that revision;
3. every claimed slug's `history/<slug>.json` holds Accepted code, or 24 h
   passed since the row (`evidence.CODE_WAIT_S`).

## One analysis, no retry

`run.analyse` measures every solve by code, then makes ONE draft-tier call.

- **One-shot:** no non-Accepted submission before the first Accepted, and no
  coach hint (`rungs`) or `revealed` on the slug.
- **Post-theory:** the first Accepted came after the unit's theory was first
  done (each module's first signed `done: true`, the latest of them). Only
  post-theory misses are preparation gaps; pre-theory solves are the baseline.
- **Kept cards:** cards whose idea a post-theory one-shot used (with none, any
  one-shot). Code decides this, and a kept card is never edited or suspended.

A failure logs a warning, writes nothing but the failed marker, and files the
todo task `Post-mortem <unit> failed` at once, whose body holds
`python -m tutor postmortem <unit> --retry`. That command removes the marker;
nothing else retries.

## Applying it (`apply.apply`)

No caps. In order: add new cards (each on its own seeded source under
`https://postmortem.leetcode-coach.invalid/<unit>/<rev>/<hash>`), edit cards
(and append an `untaught` event for each taught one: a rev bump alone
un-teaches nothing), suspend cards (the reason goes in the report). A refused
operation is recorded and logged, never raised. The new and untaught cards
make `module_state`'s reconcile sign `done: false`, so the unit is current
again and returns to THEORY; the lock keeps its Open rows, escape hatch and
break-glass.

## The re-pass credit

The usual per-minute theory credit pays the re-pass. The guard also mints
`theory-redone:<subject>:<unit>:<rev>` (amount 1) once per C7 row when, in
one poll: the unit is current (or was when the poll began), each of its
modules has a signed `done: false` after the revision's `at` followed by a
latest `done: true` signed today, and the id is not in the ledger.

## Future modules and skills

`lessons.json` holds per revision `fix` patterns and `keep` card shapes
(opening question, toy example, length). `draft_prompt` adds them to every
card draft of the subject, with no approval step.

The rest is a proposal: one normal todo task per revision, `Apply post-mortem
<unit>: future modules + skills` in project tutor, listing every proposed card
per future module and the skill proposal. Its spec stage is kuhy's approval;
then `python -m tutor apply-postmortem <unit>` regenerates each listed module
with no taught card and adds the approved cards.

## Dry run

`python3 -m leetcode_guard --postmortem-dry-run <unit>` signs a
`unit_preview` row and runs `python -m tutor postmortem <unit> --dry-run`.
That starts `tutor-postmortem-dry-<unit>` as a `systemd-run --user` unit and
answers 75 (pending) until the result for that request is on file; call
again. It writes only `postmortems/dry/<unit>.json`.
