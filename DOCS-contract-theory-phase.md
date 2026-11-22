# Tutor contract: C3, the guard's theory phase gates teaching (2026-11-22)

leetcode-guard writes this file; the tutor only reads it. It says which modules
of the two gated LeetCode subjects the tutor may teach right now. C2 (the
tutor's signed done state of a module) is in `DOCS-contract-module-state.md`.

## File
`$TUTOR_THEORY_PHASE` (live: `~/.local/share/leetcode_guard/theory_phase.json`),
one bare signed row, rewritten by the guard when the phase changes:

```json
{"kind": "theory_phase", "entry_id": "phase", "day": "YYYY-MM-DD",
 "detail": {"unit": "<unit id or empty>", "phase": "theory",
            "teachable": [["<subject>", "<module>"]], "at": 1795000000.5},
 "hmac": "<hex>"}
```

- `hmac`: HMAC-SHA256 with `/etc/workout-locker/hmac.key` (`TUTOR_KEY` in
  tests) over the row without `hmac`, `json.dumps(body, sort_keys=True,
  separators=(",", ":"))`. The guard signs it with
  `gatelock.log_integrity.compute_entry_hmac`; the tutor verifies it with
  `earned_time.verified` (`tutor/tests/test_theory_phase.py` signs its fixtures
  with gatelock).
- `phase` is `theory`, `solve` or `none`. Only `theory` grants anything; a
  `solve` or `none` row with a non-empty `teachable` is treated as malformed.
- `day` is not checked: the tutor honours the last signed phase.

## Reader (`tutor/curriculum/theory_phase.py`)
- Gated subjects: `leetcode-easy-algorithms-in-typescript` and
  `javascript-and-pandas-for-leetcode-easy` (`GATED`). Every other subject,
  `mysql-8-for-timed-sql-coding-tests-joins-and` included, is never gated and
  never reads the file.
- Fail closed: a missing or unreadable file, an unreadable key, a bad signature,
  a wrong `kind`, or a malformed `detail` means nothing is teachable and raises
  nothing. It logs ONE warning per failure: the server reads the file on every
  plan publish, so the same failure is logged again only after a good read or
  a different failure (tutor-internal; the file format is unchanged).

## The gate
A card of a gated module that is not in `teachable` is never taught and never
marked taught. Each refusal reuses an existing state; no new text is shown.

| Entry point | Refusal |
|---|---|
| `Engine.start` (`/api/start`, relay `session_start`), struggle help included | `SubjectSource.pick`: the next-card scan skips the module; an explicit card raises `no_card_left`, checked before the daily cap so "Learn more anyway" is never offered |
| `CardFlow.next_card`, `EditFlow._leave_removed` | the same pick |
| `Engine.reply` on a live card whose module became refused | the pick's `no_card_left`, before the model runs |
| `Engine.resume_path` (`resume_latest` at startup, `resume_session`) | not resumed; `resume_session` raises its existing "cannot be continued" |
| `CardFlow.continue_subject` | no open session found, so `session_start` falls through to a new start (refused as above) |
| `FollowUpFlow.follow_up_open` | the existing "cannot be continued" `ValueError` |
| `CardFlow.set_card_done` (relay `card_done`), `SubjectSource.mark` | `locked` (`done=False` is never gated) |
| the tutor's own `card_done` in `CardFlow._apply` | logged as `card_done_refused`, not marked (the phase moved mid-turn) |
| `sql_cards` seeding with `--subject` naming a gated subject | cards are added, never marked taught |

Not gated: app reviews, the PC drill and un-teaching. They act on cards that are
already taught. Taught events mirrored from RTDB are not gated either; they
have already happened on another device.

## Unit order beats plan order (`pick.unit_order_wins`, 2026-11-22)
The module gate (`DOCS-contract-curriculum.md` §6) opens a module's first card
only once every earlier plan module is fully taught. The guard's unit order
starts at `prefix-sums`, which is not the plan's first module, and C3 refuses
every earlier one, so the two gates together would never open it. The rule:
an earlier module C3 refuses now is not counted as "still to teach".

Nothing else of the module gate changes. Taught cards of earlier modules,
refused or not, must have passed a review, and no card of the subject may be
due: the refusal lists them in `gate_cards`, the app reviews them and sends
the start again. A teachable earlier module (a unit of several modules) still
holds the next one until it is fully taught. Ungated subjects refuse nothing
and keep the plan order.

## Plan payload (for the plan screen's lock glyph)
`subjects/<subject>/plan` in RTDB gives each module of a gated subject a boolean
`teachable` (`theory_phase.overlay` at publish time; `plan.json` never stores
it). A phase change re-PUTs only the plan at the same rev and moves
`rev.catalog`. Ungated subjects have no such key.
