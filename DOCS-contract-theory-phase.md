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
- `detail.theory_since` (guard, 2026-11-22): when THEORY of the unit began.
  The guard pays only teaching minutes that ended after it; the tutor
  ignores it, like any other key it does not read.

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
| `Engine.start` (`/api/start`, relay `session_start`), struggle help included | `SubjectSource.pick`: the next-card scan skips the module; an explicit card raises `no_card_left`, checked before the module gate: passing a review does not open it |
| relay `session_start` with `module` (C4 below, `learn_module.start`) | the same pick, kept to that module: `no_card_left`; an open session on a refused module's card is not reused |
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

The same rule covers a card's `requires`. A required card in a module C3
refuses now does not hold the card shut: its unit comes later in the guard's
order, so waiting would leave the module never done (measured 2026-11-22:
`histogram-prefix-sorted-position` of `prefix-sums` needs
`direct-index-counting-array` of `hashing`). A required card in a module C3
does not refuse still blocks, and ungated subjects keep every prerequisite.
One function applies the rule, `gating.missing(card, done, waived)`, with
`CardSource.waived()` naming the refused modules' cards. The pick, the tutor's
`card_done` (`phase_gate.blockers`), the manual mark (`set_card_done`) and the
card listing all call it, so a card the pick offers can always be finished
(2026-11-22: the done-gate had kept its own copy, and `card_done` was refused).
A module's done row (C2) follows from the taught cards, and the app only shows
what the worker sends.

## C4: `/learn/<subject>/<module>`, the lock's learn button
The guard runs `~/.local/bin/tutor --route /learn/<subject>/<module>`
(`run.sh`). The app opens the Session screen and sends `session_start` with
`subject`, `module` and a null `card` (`DOCS-contract.md` §4). The worker
(`tutor/learn_module.py`) then:

1. reuses the live or open session whose card is an untaught card of that
   module (never a second session on it);
2. otherwise starts a session on the module's next untaught card.

Fallbacks:
- The worker answers `no_card_left` when C3 refuses the module, when the
  module has no cards yet, is fully taught or is unknown. The app then shows
  that subject's plan screen instead of the Session (`nav.learnRefused`: it
  does the same on `locked`, `unknown_card` and `bad_request`).
- A refusal that lists `gate_cards` (the module gate, curriculum §6) first
  opens that review, as for any start. Passing it sends the start again.
- Any other failure (an outage, a model error) stays on the Session screen.
- An unknown subject stays on Home (as `/learn/...`).

### Window hand-over
Chrome hands every launch to the browser that already runs the tutor's
profile, and that browser opens a second `--app` window. A used window cannot
close itself, so the new window gives its route to the old one:

1. `run.sh` asks i3 to focus the open tutor window
   (`i3-msg '[class="^tutor$"] focus'`, 2 s limit). i3 switches to that
   window's workspace. No tutor window or no i3: the launch goes on anyway.
2. The new window, before Flutter boots (`app/web/index.html`), posts
   `learn <route>` on the BroadcastChannel `tutor-window`.
3. The open window (`deep_link_web.joinWindows`, `RouteInbox`) answers
   `took <route>` and opens the route over its current screen.
4. The new window closes itself. With no answer within 1 s, or when the
   browser refuses the close, it boots and opens the route itself.

Only `/learn/...`, `/review/...` and `/rework/...` routes are handed over
(`deep_link.handedOffer`, `web/index.html` and `run.sh`'s i3 focus step all
list the same three prefixes). The channel is per origin, so a sandbox on
another port never hears the live window.

## C5: `/review/<subject>/<module>`, the lock's review of a module
The guard runs `~/.local/bin/tutor --route /review/<subject>/<module>`. It is
handed to an open window like `/learn/...` (above), and on a cold start it
opens from Home like any deep link. The app (`nav.openModuleReview`) opens
Review on that module, the same screen as "Review this module" on the plan:
the module's taught cards not yet passed (no Good/Easy since taught), due or
not, flagged and suspended ones left out, Again/Hard requeued
(`review_items.moduleItems`). No request goes to the worker and no text is new.

Fallbacks, none of them a blank or error page:
- The module has nothing to review (nothing taught, all passed, no cards) or
  the plan lacks the module: that subject's plan screen.
- An unknown subject stays on Home (as `/learn/...`).
- `/review` alone, or with one segment, is the old due queue of every subject.

`TUTOR_DESKTOP_PORT` points `run.sh` at a sandbox server instead of
`tutor.service`'s 8778 (`scripts/e2e_i3_handover.sh`). `run.sh` never starts
a sandbox: it exits 1 when nothing answers on that port.

## Plan payload (for the plan screen's lock glyph)
`subjects/<subject>/plan` in RTDB gives each module of a gated subject a boolean
`teachable` (`theory_phase.overlay` at publish time; `plan.json` never stores
it). A phase change re-PUTs only the plan at the same rev and moves
`rev.catalog`. Ungated subjects have no such key.
