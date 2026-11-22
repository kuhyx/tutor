# Agent E2E: the `/learn` flows F22-F27

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
# F27: under i3 the open window comes to the focused workspace
$S up --phase "theory $LC/prefix-sums"
scripts/e2e_i3_handover.sh     # optional argument: where to save the shot
$S down
```

- `wait` exits 75 while the tutor's turn is pending, and F22's `idle` exits 75
  until a minute has passed since the tutor's message (a C1 row needs one
  active minute). Call the same command again.
- F22's `check` fails with "module already done before Mark card done" when
  the tutor ends the card itself on the flow's reply (the model's choice,
  seen 2026-11-22). The C1 row and the C2 flip are then already written and
  the flow has no tap left to test: run F22 again on a fresh `up`.
- `up --phase "MODE [S/M ...]"` writes the guard's C3 row into the sandbox,
  signed with the sandbox key. `theory S/M ...` grants those modules, `solve`
  grants none, `bad S/M` carries a wrong `hmac`, and `missing` (the default)
  writes no file. `$S phase MODE [S/M ...]` rewrites the row of a running
  sandbox.
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
