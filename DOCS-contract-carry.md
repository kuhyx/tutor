# Carry-over bank contract

Extra tutor minutes done on one day (past that day's quota) are banked and
spent automatically on later days, like leetcode-guard's credit bank.
Code: `tutor/carry.py`. Tests: `tutor/tests/test_carry.py`,
`tutor/tests/test_carry_wiring.py`.

## Balance (derived, never stored)

The balance is recomputed from the verified ledger
(`~/.local/share/tutor/ledger.json`, rows `earned_time.verified` accepts) on
every call. Nothing else holds it, so there is no state to drift.

- `quota_d` = `earned_time.tutor_quota_for(d)` (15 Tue-Thu, 30 Mon/Fri, 50
  weekend), never a copy in this repo.
- `paid_d` = verified tutor minutes whose `detail.ended_at` falls on local day
  `d`, carry rows included (`ledger_pay.paying`; one `entry_id` pays once).
- `spent_d` = minutes of the verified carry rows of day `d` in the ledger.
- `deposit_d` = `max(0, paid_d - quota_d)`.
- From `CARRY_FROM` = 2026-10-23, day by day in order:
  `balance = clamp(balance - spent_d + deposit_d, 0, BANK_CAP)`, with
  `BANK_CAP` = 100. Days before `CARRY_FROM` deposit nothing.

`spent_d` for a past day is what the ledger holds, not
`min(balance, quota_d)`. A day the worker never ran on (PC off) keeps the
balance; nothing is back-filled for it. Carry minutes count in `paid_d`, so
own minutes on a day the carry already filled are banked again in full. That
gives the same balance as spending own minutes first.

## Spend (today only)

`target` = `min(balance before today, quota_today)`. When the ledger pays
less carry today than `target`, one row tops it up:

```json
{"kind": "credit", "entry_id": "carry-2026-10-24-m20", "day": "2026-10-24",
 "created_at": 1792832400.0,
 "detail": {"session_id": "carry-2026-10-24", "block": 20, "minutes": 20,
            "ended_at": 1792832400.0, "carry": true},
 "hmac": "..."}
```

- `n` in `carry-<day>-m<n>` is the day's cumulative target and `minutes` the
  delta over the carry already paid. These are the same semantics as a
  session's `-m<n>` rows.
- A rerun finds `target <= prepaid` and writes nothing. Every ledger write
  fires screen-locker's `earner-bonus.path`, so an idle pass must not write.
- A larger target later the same day writes only the delta under a new id.
  This happens when yesterday's late phone reviews are paid after midnight
  (`review_credit`, `_DAYS_BACK` = 1).
- `ended_at` = `created_at` = the write time, inside today. `day` = today.
  The i3blocks counter sums rows by `.day`.
- The read, compute and append happen under the ledger lock and a
  process-wide lock, so concurrent passes spend once.
- The writer's daily trim still applies. A carry row on a day already at the
  trim is cut, and its id is never retried, so the bank keeps the rest.

earned_time counts the row unchanged: `tutor_match` needs a positive int
`minutes` and `ended_at` in the day window. Nothing reads `entry_id`'s shape,
`block`, `carry` or `session_id`. Its own clamp is unchanged:
`min(60, minutes * 60 // quota)` units a day.

## Writer trim

`ledger_pay.DAILY_CAP_MINUTES` = `EARNER_CAP_MINUTES` (60) + `BANK_CAP`
(100) = 160. The writer records up to 160 minutes a day, so extra minutes
exist in the ledger to be banked. `stats.days[*].minutes` can now exceed 60.
`stats.today.credited_minutes` stays clamped at 60.

## Who spends

Only the live worker (`tutor/relay`), with its own clock:

- at startup (`Relay.start`, beside the Anki watch, not waiting on RTDB);
- on every curriculum sync (about 60 s, and around every request), right
  after the app-review credit pass;
- before it publishes `stats` (`Publisher.stats`).

`curriculum.stats.stats()` only reads the bank. An HTTP-only server
(`TUTOR_RELAY=0`, the deploy smoke test) never spends. The smoke test and
the E2E sandbox run on a data-dir copy without `ledger.json` and with a
throwaway key.

## Stats

`stats.today` gains two keys:

- `banked`: the balance after today so far, today's spend and deposit
  included.
- `prepaid`: the carry minutes the ledger pays today.

The app shows "Banked N min · prepaid M" next to the credited counter (the
Session header and Home), only when either is > 0. An older worker sends
neither key.
