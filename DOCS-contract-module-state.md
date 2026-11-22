# Tutor contract: C2, the signed done state of a module (2026-11-22)

leetcode-guard's theory-first lock reads this file to learn whether the theory
of a unit is done. The tutor writes it; the guard only reads it. C1 (the
`subject`/`module` keys on teaching rows) is in `DOCS-contract.md` §7.

## File
`$TUTOR_DATA/module_state.json` (live: `~/.local/share/tutor/module_state.json`):

```json
{"version": 1, "entries": [
 {"kind": "module_state", "entry_id": "state:<subject>:<module>:<n>", "day": "YYYY-MM-DD",
  "detail": {"subject": "<slug>", "module": "<module id>", "done": true, "at": 1795000000.5},
  "hmac": "<hex>"}]}
```

- Append-only. A row is never rewritten or removed.
- `hmac`: HMAC-SHA256 with `/etc/workout-locker/hmac.key` (`TUTOR_KEY` in
  tests) over the row without `hmac`, `json.dumps(body, sort_keys=True,
  separators=(",", ":"))`: `earned_time.entry_signature`, the same signer as
  `credit.py`. `gatelock.log_integrity.verify_entry_hmac` verifies it
  (`tutor/tests/test_module_state.py`).
- `n` is 1 + the number of rows already on file for that (subject, module),
  verified or not, so an `entry_id` never repeats.
- `at`: Unix seconds (float) of the change; `day`: the PC-local date of `at`.
- `done` is true when the module has at least one live (not suspended) card
  and every live card is taught, by the fold of the raw event log
  (`DOCS-contract-curriculum.md` §4). Archiving a subject does not change it.
- The latest verified row per (subject, module), in file order, wins. No
  verified row means not done.

## Who writes, and when (`tutor/curriculum/module_state.py`)
Rows are written only for the three subjects of the LeetCode course:
`leetcode-easy-algorithms-in-typescript`, `javascript-and-pandas-for-leetcode-easy`
(both gated by C3) and `mysql-8-for-timed-sql-coding-tests-joins-and`.

- `Context.subjects` and `Context.log` hand out `WatchedStore` / `WatchedLog`.
  After every commit that writes a subject's cards, and after every stored
  `taught`/`untaught` event, the writer recomputes `done` for every plan module
  of that subject and appends a row for each module whose truth differs from
  its latest verified row. A module with no row that is not done gets none.
  This covers a card marked taught or un-taught (`SubjectSource.mark`, the SQL
  seed, an event mirrored from RTDB), cards added by generation (`cardgen`),
  cards suspended by regeneration (`regen`), and every other card commit
  (split, edit, undo, redraft).
- Startup (`python -m tutor`, `python -m tutor worker`) runs
  `Engine.record_module_states()`: every plan module of the three subjects
  with no verified row gets its current truth, done or not, and any module
  whose truth drifted (a change made outside a `Context`) gets a row. A second
  start writes nothing.
- The writer holds `module_state.lock` while it reads, decides and appends.
- A failure (no signing key, an unreadable or corrupt file) logs a warning and
  writes nothing. It never reaches teaching: the event or commit it follows has
  already landed.

## Reader rules (leetcode-guard)
- One rule for a bad row (decided 2026-11-22, guard `DOCS-theory-first.md`
  says the same): a row whose signature fails makes the whole file "cannot
  check". The guard does not skip it. Skipping could only hide a later
  `done: true` row, so the module reads as not done and its theory pays
  again. A signed row that is not `kind: module_state` or has no valid
  `detail` is skipped; it is not a C2 row.
- "Cannot check" is not "not done": the guard keeps its last signed phase,
  mints no theory credit, and solves still pay. The lock keeps its Open
  rows, escape hatch and break-glass (the THEORY card is only a slot).
- The writer never appends an unsigned row (no key: it writes nothing), so a
  bad row comes only from outside the tutor. To recover, delete that row by
  hand: what is left is signed, so deleting it gains nothing.
