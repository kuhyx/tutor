# Agent E2E: the `/learn` flows F22-F28, the rework chat F29, F30 and F31

These flows drive the LeetCode lock's learn button from the route to the
signed rows. The sandbox is described in README "Agent E2E"; the contracts
are in `DOCS-contract-theory-phase.md` (C3, C4), `DOCS-contract.md` §7 (C1)
and `DOCS-contract-module-state.md` (C2).

Run each command as its own call from the repo root; each ends in under 60 s.
Every flow needs a fresh `up`. None takes `--as-of`: F22 and F24 run a model
turn, and a faked clock breaks the model. Exit 0 = PASS.

```bash
S=scripts/e2e_sandbox.sh
LC=leetcode-easy-algorithms-in-typescript
SQL=mysql-8-for-timed-sql-coding-tests-joins-and
$S build                       # once per app change (~35 s)

# F22: the route teaches a granted module, pays a C1 row, flips C2 to done
$S up --learn $LC/prefix-sums --phase "theory $LC/prefix-sums"
$S flow F22 send               # then, one call each: wait, again, idle,
                               # reply, wait, check
# F23: a module outside `teachable` is refused; the subject's plan shows
$S up --phase "theory $LC/prefix-sums"
$S flow F23
# F24: SOLVE locks every LC plan tile; the ungated SQL subject still teaches
$S up --phase solve --unarchive $SQL
$S flow F24 send               # then: wait, check
# F25: no C3 file, then a badly signed one: refused, one warning each
$S up
$S flow F25 missing
$S flow F25 bad
# F26: a second --app window hands its route to the open one and closes
$S up --phase "theory $LC/prefix-sums"
$S flow F26
# F28: the second unit goes through the module gate first (one `up` each)
$S up --unit-gate fresh --phase "theory $LC/prefix-sums"
$S flow F28 send               # then: wait, lesson, idle, reply, wait, paid
$S up --unit-gate taught --phase "theory $LC/stack-queue"
$S flow F28 review             # then: wait, check
$S up --unit-gate taught --phase solve
$S flow F28 solve
# F27: under i3 the open window comes to the focused workspace
$S up --phase "theory $LC/prefix-sums"
scripts/e2e_i3_handover.sh     # optional argument: where to save the shot
# F29: the lock's ? rework chat adds cards; C2 flips back to done: false
$S up --phase solve --rework $LC/scans/matrix-diagonal-sum
$S flow F29 open               # then, one call each: send, wait, check
# F30: a phone review lands in log.jsonl and review_due.json in < 5 s
$S up
$S flow F30 rate               # then, after 60 s: idle (75 = call again)
# F31: a refused card_done shows the rewrite or the lock, never the draft
$S up --scripted               # the model is a queue the flow writes
$S flow F31 rewrite            # then: fallback (same sandbox)
E2E_SUBJECT=$LC $S up --scripted --learn $LC/prefix-sums --phase "theory $LC/prefix-sums"
E2E_SUBJECT=$LC $S flow F31 module
$S down
```

- F30 (`scripts/e2e_log_wake.py`, no browser) plays a phone: a fresh device
  writes review events to `log/{dev}` on the emulator, sealed as the app
  does. `rate` prints the write -> `log.jsonl` delay of three ratings and the
  write -> `review_due.json` mtime delay of a fourth, and fails over 5 s, so a
  change that brings back the 60 s poll goes red. `idle` checks that the
  worker's own `log/` node stayed still and its CPU low for 60 s (no sync
  loop from its own push).
- `up --scripted` swaps the Claude CLI for `scripts/e2e_script_session.py`:
  each model turn is the next entry of `<sandbox>/model_script.json`, and
  every prompt the engine sent goes to `model_script.prompts.jsonl`. The
  engine, relay and app are the real ones. F31 `rewrite` starts a card whose
  requires are taught, then a second device marks one of them not done;
  `module` holds the draft while it moves the guard to `solve`
  (`scripts/e2e_done_refusal.py`).

- `wait` exits 75 while the tutor's turn is pending, and F22's `idle` exits 75
  until a minute has passed since the tutor's message (a C1 row needs one
  active minute). Call the same command again.
- F22's `check` passes on either path: the tutor may end the card itself on
  the flow's reply (the model's choice). Then the C2 row is already written
  and the flow skips "Mark card done"; `send` refuses a module that was done
  before the flow started, so that row is always the flow's own.
- `up --phase "MODE [S/M ...]"` writes the guard's C3 row into the sandbox,
  signed with the sandbox key. `theory S/M ...` grants those modules, `solve`
  grants none, `bad S/M` carries a wrong `hmac`, and `missing` (the default)
  writes no file. `$S phase MODE [S/M ...]` rewrites the row of a running
  sandbox.
- `up --guard-theory '<json>'` serves a canned `GET /api/theory` `theory` map
  (`DOCS-contract-leetcode-bar.md`) on a sandbox port for the LeetCode bar; a
  missing `day` is today's. Without it the sandbox server's route is a closed
  port (numbers `?`); it never reads the live guard.
- `up --learn S/M` teaches every card of module M but one, so the flow's one
  card finishes the module.
- `up --unarchive S` unarchives subject S in the copy. kuhy keeps SQL
  archived, and a route into an archived subject stays on Home.
- F22-F26 run Chromium on the Xvfb named by `E2E_DISPLAY` (default `:97`,
  3840x2160). F27 starts its own Xvfb and its own i3 from kuhy's config
  without the bar and the `exec` lines. It never touches his display or his
  i3 socket, and it saves the Xvfb root to
  `app/build/screens/e2e_i3_handover.png`: Read it.
- Flow ids moved up by one on 2026-11-22, when F21 became the module gate's
  flow: old F21 -> F22, F22 -> F23, F23 -> F24, F24 -> F25, F25 -> F26,
  F26 -> F27. Six older commit subjects still carry the old ids.
- F21 (README "Agent E2E") needs `E2E_SUBJECT=product-and-design-taste` on
  every call on today's data: the default subject has no unstarted module
  after a taught one, so `up --gate` refuses to seed it.
- F29 (`e2e_rework.py`): `up --rework S/M/SLUG` writes a synthetic guard
  history of SLUG (two submissions with code) to `<sandbox>/guard`, which the
  sandbox server reads as `TUTOR_GUARD_DATA`, and teaches the rest of M, so
  a row verified with the sandbox key reads `done: true` (the copied rows
  are signed with the real key; with no verified row, the rework's new card
  writes no `done: false` row at all). `scans` is the guard's unit for
  matrix-diagonal-sum's tags (array, matrix). `open` asserts the
  `rework_open` result counts the seeded submissions and saves the baseline;
  `check` run right after `open` is the red run (no rework card). `check`
  wants a new card of M with `tutor.source == "rework:SLUG"` and a new
  verified C2 row of M reading `done: false`, then saves the reopened chat
  as `app/build/screens/e2e_f29_rework.png`.
