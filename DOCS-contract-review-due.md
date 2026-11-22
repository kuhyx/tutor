# Tutor contract: C4, the signed due times of a module's review queue (2026-11-22)

leetcode-guard's lock reads this file to learn how many card reviews of a
module are due, at any time T, without the tutor running. The tutor writes it;
the guard only reads it. The queue's due dates come from the unsigned log fold
(`DOCS-contract-curriculum.md` §4/§5), which the guard may not decide from; the
tutor publishes the result as a signed fact. Envelope, signer, lock and atomic
write are C2's (`DOCS-contract-module-state.md`).

## File
`$TUTOR_DATA/review_due.json` (live: `~/.local/share/tutor/review_due.json`):

```json
{"version": 1, "entries": [
 {"kind": "review_due", "entry_id": "due:<subject>:<module>:<n>", "day": "YYYY-MM-DD",
  "detail": {"subject": "<slug>", "module": "<module id>",
             "due_ms": [1795538726572, 1795538750796], "at": 1795371048.89},
  "hmac": "<hex>"}]}
```

| Field | Type | Meaning |
|---|---|---|
| `kind` | string | always `"review_due"` |
| `entry_id` | string | `due:<subject>:<module>:<n>`; `n` is 1 + the greatest `n` ever seen for that (subject, module) in the file before the write |
| `day` | string | PC-local date of `at` |
| `detail.subject`, `detail.module` | string | ids (no `:`) |
| `detail.due_ms` | array of int | the `due` of each card in the module's queue, **Unix time in milliseconds, UTC**, ascending, one per card, duplicates kept; `[]` when the module has none |
| `detail.at` | number | Unix **seconds** (float) of the write |
| `hmac` | string | HMAC-SHA256, hex |

Example (real data, 2026-11-22, a rehearsal copy): module `prefix-sums` of
`leetcode-easy-algorithms-in-typescript`, ten taught cards, none due yet:

```json
{"kind":"review_due","entry_id":"due:leetcode-easy-algorithms-in-typescript:prefix-sums:1","day":"2026-11-22","detail":{"subject":"leetcode-easy-algorithms-in-typescript","module":"prefix-sums","due_ms":[1795538726572,1795538750796,1795538766305,1795538879977,1795538918994,1795538936883,1795538970483,1795538980860,1795539031998,1795543167023],"at":1795371048.8916335},"hmac":"<hex>"}
```

An empty module: `"due_ms": []`.

## Meaning
- `due_ms` lists the cards of the module that the tutor's own review queue
  holds (`no_card.due_in_subject`, §5): the card is **taught**, **not flagged**
  at its current `rev`, **not suspended**. Its `due` is the folded FSRS due
  (`fsrs_state()["due"]`), exact in ms.
- **Due at T** is `due <= T` (T in ms). The count of cards due at T is the
  number of `due_ms` entries `<= T`. No clock, fold or FSRS is needed.
- A module of the plan with no queue card (nothing taught, all flagged or
  suspended, no cards at all) has an explicit row with `[]`. Only a module
  with NO row is "never written".
- An **archived** subject has `[]` for every module (the app and the queue hide
  it); unarchiving rewrites the rows.
- Cards of a module id that is not in the subject's plan are not listed.
- Subjects: the three of C2 (`module_state.SUBJECTS`): the two LeetCode ones
  and the SQL one.

## Rows: latest wins, one per module (differs from C2 on purpose)
C2 is append-only. This file is **latest-row-wins per (subject, module)** and
the writer keeps exactly one row per module: it **replaces** the module's row
(and drops any other row of that module, verified or not) and keeps every other
row byte for byte. Reason: a row is rewritten on every review, so appending
would grow the file and the guard's verification cost without bound. If a file
somehow holds several rows of a module, the one with the greatest `at` wins
(the later in the file on a tie); an older signed row replayed later loses.

## Who writes, and when (`tutor/curriculum/review_due.py`)
All of it for the three subjects only; nothing polls.
- `Context.log` (`WatchedLog.append`): after every newly stored event of such a
  subject, whatever its kind: `taught`, `untaught` (manual card toggle,
  repair), `review` (app, drill, check-in, mirrored from RTDB), `flag`,
  `review_undo`, `subject_archive`, `subject_unarchive`.
- `Context.subjects` (`WatchedStore.commit`): after every commit that writes
  the subject's cards (suspend, un-suspend, edit and its rev bump that clears
  a flag, split, generation, regeneration, redraft) or its plan (a new module
  gets its empty row).
- Startup (`python -m tutor`, `python -m tutor worker`):
  `Engine.record_module_states()` also calls `review_due.backfill`, so the
  file exists after the next deploy and any drift is repaired.
- The writer recomputes the due list of every module of that subject and
  replaces only the rows whose `due_ms` changed (or are missing). No change
  writes nothing, not even a new `n`.
- It holds `review_due.lock` (flock) while it reads, decides and writes, and
  writes by temp file + fsync + rename: a reader sees the old file or the new.

## Failure modes (writer side)
- No signing key, an unreadable or corrupt file, a full disk: a warning
  (`review due of <subject> not recorded: ...`) and nothing written. It never
  reaches teaching or reviewing: the event or commit it follows has already
  landed. The file then stays as it was (stale) or missing.
- **Stale file**: written only on the events above, so a failed write leaves
  old rows. Due times are absolute, so a stale row still counts every card it
  lists correctly; it can only miss what changed after it: a card taught after
  it, or a review that pushed a card's `due` later (the stale row then reads
  that card as due earlier: more due, never fewer). A card suspended or flagged
  after it still counts as due.

## Tamper notes
- The signature proves the row was written by a holder of the signing key (the
  tutor, as root-readable `/etc/workout-locker/hmac.key` via `earned_time`)
  and not edited since. It proves nothing about freshness: an old signed row
  can be put back.
- Deleting a row, or the file, cannot be told from "never written": the reader
  must treat it as "cannot check", never as "nothing due".
- Putting back an older copy of the file hides only cards taught after the
  copy; reviews only move `due` later, so an old row lists earlier dues.
- A reader that skipped a row failing verification could hide the row that
  carries due cards, so it must not skip.

## Reader rule (leetcode-guard)
1. Read `review_due.json`; missing, unreadable, not JSON or no `entries` array: cannot check.
2. Verify every entry with `earned_time.verified` / `gatelock.log_integrity.verify_entry_hmac`; one entry that is not a dict or fails: the whole file is "cannot check" (do not skip it).
3. Skip verified rows whose `kind` is not `review_due` or whose `detail` lacks `subject`/`module` (strings), `due_ms` (list of ints), `at` (number).
4. For (subject, module) take the row with the greatest `at` (later in the file on a tie); no such row: cannot check.
5. Due at T (ms) = count of `due_ms` entries `<= T`; "cannot check" is not "nothing due": keep the last signed state, show the problems anyway.

The tutor's own reference reader is `review_due.read_due(rows, key)` and
`review_due.count_due(path, key, subject, module, at_ms)` (`None` = cannot
check), tested in `tutor/tests/test_review_due_checks.py`, which also checks the C2
helpers verify a row and a forged row fails.
