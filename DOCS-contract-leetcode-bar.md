# Tutor contract: the LeetCode bar, `sessions/{sid}/meta/leetcode` (2026-11-22)

A lesson that counts as LeetCode theory shows LeetCode accounting in the app's
top bar. The worker adds an optional map to the session meta
(`DOCS-contract.md` §6); every other session has no such key and the app
paints its bar unchanged.

**Display only.** Nothing that pays, caps or refuses a turn may read this map
or `tutor/leetcode_bar.py`: a lesson is credited the same whether the guard
answers or not (`DOCS-contract-theory-phase.md` is what gates teaching).

## When a session has the map
All hold, or the key is absent:
1. the guard's signed phase (`theory_phase.current()`, fails closed: a file
   that cannot be verified is "no theory session") is `theory`,
2. the session's current card belongs to a `(subject, module)` pair in its
   `teachable` list (so only the two gated LeetCode subjects can qualify), and
3. the session is the engine's live session and is not stopped. Every other
   publish (history, a republish at startup, a stopped session) writes
   `leetcode: null`; when the live session stops or a new one starts, the
   previous session's map is removed at its next publish and by the 30 s
   tick. The app also paints the bar only while `meta.stopped` is false.

## Wire
```json
"leetcode": {"unit": "prefix-sums", "taught": 3, "total": 9, "full": false,
             "into": 7, "per_credit": 12, "credits": 0, "needed": 7}
```
- `unit`: the signed phase's unit. `taught` / `total`: live (not suspended)
  cards of the card's module, taught / all, from the tutor's own cards and
  event log. `full`: today's ledger minutes reached
  `ledger_pay.DAILY_CAP_MINUTES` (no further minute can be recorded today).
- `into`, `per_credit`, `credits`, `needed` are the guard's, from
  `GET http://127.0.0.1:8771/api/theory`:
  `{"theory": {"checked", "day", "unit", "phase", "minutes_today",
  "minutes_into_credit", "minutes_per_credit", "credits_today", "needed"}}`.
  `minutes_into_credit` -> `into`, `minutes_per_credit` -> `per_credit`,
  `credits_today` -> `credits`, `needed` -> `needed`.
- **Could not check means the key is omitted, never 0**, and the app paints
  `?`: route down, timeout (0.5 s), a status other than 200, bad JSON, no
  `theory` map, `checked` not true, `phase` not `theory`, `day` not today
  (tutor's local day), a `unit` other than the signed phase's, or a number
  that is null, not an integer, a boolean, negative, above 10000, a
  `per_credit` below 1, or an `into` above `per_credit` (only that number is
  left out, never clamped; `0` is a number). A `unit` that is not a string
  counts as another unit. `unit`, `taught`, `total`, `full` are tutor data and
  stay. Nothing the guard sends raises out of `session_map`.

## Fetching (`tutor/guard_route.py`, `tutor/leetcode_bar.py`)
- stdlib `urllib` on a one-worker pool: the whole fetch has a 0.5 s TOTAL
  deadline (a dripping server cannot stretch it), the body is read in chunks
  and refused above 4096 bytes, and no exception reaches a turn. A failure
  (incl. `BadStatusLine`, `IncompleteRead`, a nested-JSON body) turns the
  route off for 30 s; a success is served from a 5 s cache. The URL is read at
  call time from `TUTOR_GUARD_THEORY_URL` (default the route above).
- One warning per state change (reachable -> unreachable, and back), not per
  call. A reachable route whose answer is "not checked" is not an outage.
- Refresh hooks: `Publisher._session` (the session's start, open and every
  turn's publish: `after`, `startup`, a web-page turn caught by `refresh`) and
  the relay's 30 s `_refresh` tick, which asks again for the live session at
  most once per 60 s and rewrites only `meta/leetcode` when it changed
  (deleted when the session stops qualifying). The projection writes a `null`
  for the key whenever there is no map, so a map from an earlier phase never
  lingers.

## Tests and the sandbox
- `tutor/tests/conftest.py` (`guard_theory`, autouse) points the env at a fake
  and answers only it; the live `127.0.0.1:8771` is an `AssertionError`.
- Agent E2E: `scripts/e2e_sandbox.sh up --phase "theory S/M" --guard-theory
  '<theory map JSON>'` serves the map on a sandbox port
  (`scripts/e2e_guard_stub.py`; a missing `day` is filled with the sandbox's
  today). Without the flag the sandbox server's route is a closed port, so the
  numbers read `?`; it never reads the live guard.
