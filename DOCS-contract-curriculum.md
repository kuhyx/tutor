# Tutor contract: curriculum, cards, FSRS, unlock (v1)

Companion to `DOCS-contract.md` (paths under `/tutor/v1`). B2 owns the logic
and `contract/fsrs_vectors.json`; B3 implements the same fold in Dart and must
pass the same vectors.

## 1. Subject: `subjects/{subj}/meta` (worker)
```json
{"title":"How a car works","goal":"I want to learn how a car works",
 "status":"draft","created":ms,"plan_rev":2,"rev":7,"origin":"generated"}
```
- `status`: `drafting -> draft` (awaiting approval) `-> active -> completed`;
  then `go_deeper` returns to `draft` with new modules appended, or
  `review_only`.
- `rev` bumps on any change under the subject (and `rev.catalog` with it).
- Many subjects active at once; reviews from all; new material from
  `prefs.current_subject` (picked on Home).
- `subject_new`: worker writes `meta` with `status:"drafting"` at once, then
  the plan when the model is done.

## 2. Plan: `subjects/{subj}/plan` (worker)
```json
{"rev":2,"status":"draft","notes":"why this order (<=600 ch)",
 "modules":[{"id":"engine-basics","title":"The four-stroke engine",
   "summary":"<=300 ch","requires":[],"depth":1,"prefixes":[],
   "status":"locked","recall":0.0,"cards":0,"error":null}],
 "history":[{"rev":1,"comment":"less history","at":ms}]}
```
- Array order = teaching order. `requires` subset of earlier module ids (DAG,
  validated). 3-12 modules per draft. `depth` = go-deeper round (1 = first
  plan). `prefixes` optional (automation id rule).
- Module `status`: `locked | generating | ready | mastered | failed`; `failed`
  carries `error`; `plan_approve` (same rev) retries it.
- `plan_edit` sends the full module list (validated, unknown keys dropped);
  `plan_revise` sends a comment and the model redrafts. Both only while
  `status:"draft"` and only for modules without cards. Every plan op carries
  `plan_rev`; mismatch -> `plan_conflict`.
- `plan_approve` -> `status:"approved"`, subject `active`; modules whose
  requires are met unlock, generation starts.
- `go_deeper` (after `completed`): new rev, `status:"draft"`, existing modules
  kept verbatim, new ones appended with `depth+1`; needs approval again.
  `review_only` -> subject `review_only`, nothing new.

## 3. Card: `subjects/{subj}/cards/{cid}` (worker)
```json
{"module":"engine-basics","order":3,"front":"<=25 words","back":"<=30 words",
 "source":"https://...","excerpt":"6-40 words, verbatim from source",
 "requires":[],"rev":1,"origin":"generated","created":ms,"suspended":false}
```
- Rules as `plc_lab.cards` today: https source; excerpt verified verbatim in
  the fetched page text (`sources.check_excerpt`, normalised); `requires` are
  same-subject card ids, acyclic.
- Ids never renamed, cards never deleted (`suspended:true`). `origin`:
  `seed | generated | edited`.
- Just-in-time generation when a module unlocks (`generating`): worker finds
  and fetches >=2 sources (cached like `sources.py`), model drafts 6-12 cards
  from them; only excerpt-verified cards kept; <3 kept -> `failed`; else
  `ready` with `cards` = count.
- `card_edit` validates exactly like today's `deck_edit` (fields, word limits,
  prefixes, source fetch + excerpt check); refusal -> `edit_refused` with the
  reason; success -> `rev`+1, `origin:"edited"`. New card id = given one, else
  slug of `front`.
- Concepts: `subjects/{subj}/concepts` =
  `[{"name":"normally closed contact","at":ms,"card":"ld-x","session":sid}]`,
  array, appended by worker only.

## 4. Event log: `log/{dev}/{eid}` (append-only)
```json
{"k":"review","s":"car","c":"eng-four-strokes","r":3,"at":ms,"rev":1,"dur_ms":5400}
{"k":"flag","s":"car","c":"eng-four-strokes","rev":1,"reason":"answer is wrong","at":ms}
{"k":"taught","s":"car","c":"eng-four-strokes","at":ms,"session":"<sid>"}
{"k":"untaught","s":"car","c":"eng-four-strokes","at":ms}
```
- `review`/`flag` from any device, offline OK. `taught`/`untaught` worker
  only (tutor's `card_done`, or the manual `card_done` request).
- `r`: 1 Again, 2 Hard, 3 Good, 4 Easy. `at` = device wall clock when
  answered. `rev` = card rev shown.
- Events immutable; corrections are new events. Client queues locally, PUTs
  `log/{own dev}/{eid}` in eid order (idempotent retry); never writes another
  device's subtree.
- **Fold** (identical in Python and Dart; pure function of events + cards):
  1. Merge all devices; sort by `(at, eid)`.
  2. Drop a `review` of the same card within 60 s of an earlier kept review
     from a **different** device (deterministic offline double-tap dedupe).
  3. Per card: `taught` -> new FSRS card reviewed **Good at `at`**;
     `untaught` -> back to untaught (out of queue); `review` on an untaught
     card ignored.
  4. A `review` applies even if its `rev` differs (knowledge, not wording).
  5. `flagged(c)` iff some `flag` has `rev == card.rev`; `card_edit` bumps rev,
     clearing flags.

## 5. FSRS (pinned both sides)
- Python `fsrs==6.3.2`: `Scheduler(desired_retention=0.9, learning_steps=(),
  relearning_steps=(), maximum_interval=36500, enable_fuzzing=False)`,
  default parameters. Dart `fsrs: 2.0.1`, same settings. No fuzz, no
  short-term steps => deterministic replay on every device.
- `contract/fsrs_vectors.json` (B2):
  `[{"events":[["taught",at],["review",at,3],...],"expect":{"due":ms,"stability":x,"difficulty":y,"state":"review"}}]`;
  tolerance 1e-6, `due` exact to the second. If Dart can't match, B3 ports
  py-fsrs's Scheduler to Dart. Unlock never reads FSRS state (§6), so a
  divergence only shifts due dates.
- Review queue (client, offline): all subjects; taught, `due <= now`, not
  flagged, not suspended; sorted by `due`; no cap.
- Review screen: front -> reveal back + excerpt + source host (link) -> 4
  rating buttons + "Flag". Client caches derived FSRS state, rebuildable from
  the log at any time.

## 6. Unlock, mastery, daily cap (raw log only, not FSRS)
- `good(c)` iff c taught, and its **latest** review after the last `taught`
  has `r >= 3` and `at >= taught.at + 20 h` (real recall, not same sitting).
- `recall(m)` = good cards in m / (cards in m not flagged, not suspended); 0
  if empty. `mastered(m)` iff m was `ready` and `recall(m) >= 0.8`.
- `unlocked(m)` iff plan approved and every `requires` mastered. Modules
  without requires unlock on approve. Migrated modules with a taught card
  always unlocked.
- Worker re-folds after every log change it sees (incremental GET every 60 s
  and before every request): writes module `status`/`recall`, starts
  generation for newly unlocked modules, sets subject `completed` when every
  module is mastered (client offers "Go deeper" / "Review only").
- **Daily new cap = 10, all subjects.** New card = a `taught` event;
  `new_today` = taught events with `at` on today's PC-local date. A
  `session_start`/`next` that would teach an untaught card when
  `new_today >= 10` -> `daily_new_cap`. Re-teaching a taught card is free.
  Client shows `stats.today.new`/`new_cap`.
- Next-card pick (worker): subject = `body.subject` or
  `prefs.current_subject`; first card in (module order, card order) that is
  untaught, not flagged/suspended, card `requires` taught, in an unlocked +
  ready module. None -> `no_card_left`.
- Teaching flow unchanged: one card per session, check questions, tutor
  `card_done` -> `taught` event, then Next card / Stop here. First FSRS review
  due from Good-at-taught.

## 7. Stats: `stats` (worker)
```json
{"today":{"day":"2026-10-12","credited_minutes":23,"target":60,"new":4,"new_cap":10},
 "days":{"2026-10-12":{"minutes":23,"taught":4,"reviews":31}}}
```
`minutes` from the verified ledger (`progress.ledger_minutes_by_day`). Backs
the Progress view and the header counter.

## 8. Client screens (parity with `static/*.js`) and their data
- **Home**: subjects with `status`/progress; "new subject" free text; due
  review count; PC presence; credited x/60; new x/10.
- **Plan**: draft view + editing (rename, reorder, add, remove module without
  cards, edit requires); comment -> `plan_revise`; Approve.
- **Session**: chat from projection; per-question answer boxes (joined into
  one `message` text as `questions.js` does); check banner; images with
  attribution; diagrams; busy phase; Card done -> Next card / Stop here; Mark
  card done; Switch card; mastered list; stalled/paused pill.
- **History**: `session_index` (archived toggle, auto-archived hidden), past
  transcript view, Repeat, Continue (`session_resume`), mark card
  done/not done.
- **Progress**: `stats.days` timeline + per-module recall.
- **Editor**: subject -> module -> cards, `card_edit`, flag.
- **Review**: §5, offline.
- **Report a problem**: `feedback/`, optionally tied to one message.
