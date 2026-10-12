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
  the plan when the model is done. Subject id = slug of the text minus "I want
  to learn"-style filler (`how-a-car-works`). A failed draft sets
  `status:"failed"` + `error`; a new `subject_new` with the same text reuses
  that id.
- PC files (canonical, `tutor/curriculum/subject_store.py`):
  `$TUTOR_DATA/subjects/{subj}/meta.json|plan.json|cards.json|concepts.json|profile.json`
  (`cards.json` = id -> card in module/card order) and `$TUTOR_DATA/log.jsonl`
  (one event per line with its `dev` and `eid`). Every change bumps
  `meta.rev`, written last.
- `profile.json`: the subject's wording for the tutor's rules (domain, example
  chain, concepts, analogy, picture terms, `diagrams`). `automation` = the PLC
  wording verbatim (repo `subjects/automation/profile.json`); new subjects get
  one drafted with the plan. Only electrical subjects get schemdraw diagrams;
  the engine drops `diagram` for the others.

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
  `status:"draft"` and only for modules without cards: modules with cards (or
  not `locked`) must stay in the list and are restored verbatim. Every plan op
  carries `plan_rev`; mismatch -> `plan_conflict`. "3-12 modules" counts the
  newest `depth` only (a go-deeper draft appends).
- `plan_approve` -> `status:"approved"`, subject `active`; modules whose
  requires are met become `generating`. The worker then runs generation
  (`generate(ctx, subj, module)`) on the build lane for every module
  `fold_and_advance`/`pending` lists; a module left `generating` by a crash
  is listed again.
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
- Just-in-time generation when a module unlocks (`generating`), model with
  no tools (it only sees text) and code alternating. Every model call sees
  the plan around the module (`plan_context`): each other module's id, title
  and summary, split by plan order into earlier (already taught: their
  content is a duplicate) and later (they teach their own topic in depth):
  1. model names <= 5 canonical Wikipedia titles for the module (goal, title,
     summary), none that is another module's main article; 2. code looks those and the module title up exactly
     (`redirects=1`), then searches en.wikipedia.org (4 hits) and
     en.wikibooks.org (3) for the title and the title + 3 new summary words;
     drops disambiguation (`pageprops`), list/outline/index pages and pages
     < 1500 chars; <= 10 candidates; 3. code drops search hits whose title is
     mostly words the module never uses (`relevance.title_fit` < 0.6) and
     ranks the rest by summary-word coverage, exact-title hits first;
  4. model keeps the on-topic candidates (title + first 150 words), <= 3;
     a page whose main subject another module covers is off topic;
     < 2 -> `failed`; 5. model drafts 6-12 cards from them (<= 2500 words
     each), each fitting THIS module better than any other: another
     module's part or system only as what it is and does for the whole;
  6. code keeps the cards that pass the rules and the verbatim excerpt
     check; 7. model gates each card against the module summary and names
     the plan module it fits best (`module`, enum of the plan's ids); code
     keeps it only for `on_topic:true` AND `module` = this module (fail
     closed: no verdict -> refused; an earlier module -> "duplicates", a
     later one -> "belongs to later module"); the gate also sees the deck
     so far (live cards of this and earlier modules, id + front) and names
     in `repeats` a card there or EARLIER in the batch that asks the same
     fact -> refused (a later or self reference is ignored, so of a pair the
     first stays). < 3 kept -> `failed`;
     else `ready` with `cards` = live (not suspended) count. A chosen
     page's extract is seeded into the excerpt-check cache for the article
     URL (unless cached already), so the model drafts from exactly the text
     the check verifies; a re-check of a wiki card whose cache entry is gone
     re-seeds the extract first.
- Repair (`python -m tutor regenerate SUBJ MODULE`): step 7 over the
  module's live cards that were never taught (a taught card always stays,
  untouched), refused ones `suspended:true`, module back to
  `generating`; the worker drafts replacements (numbered after the module's
  last card, told not to repeat the suspended ones). A regeneration that
  fails leaves a module with >= 3 live cards `ready` (`error` null: only
  `failed` carries one; the fold clears a stale one on `ready`/`mastered`).
- `card_edit` validates like the old page's deck editor did (fields, word limits,
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
  2. Drop a `review` of the same card that comes **less than 60000 ms** after
     an earlier kept review from a **different** device (deterministic offline
     double-tap dedupe). Exactly 60000 ms apart: both kept. The same device
     rating twice: both kept.
  3. Per card: `taught` -> new FSRS card reviewed **Good at `at`** (a second
     `taught` resets the card's FSRS state the same way); `untaught` -> back to
     untaught (out of queue); `review` on an untaught card ignored (it never
     counts for dedupe either).
  4. A `review` applies even if its `rev` differs (knowledge, not wording).
  5. `flagged(c)` iff some `flag` has `rev == card.rev`; `card_edit` bumps rev,
     clearing flags.

## 5. FSRS (pinned both sides)
- Python `fsrs==6.3.2` (newest stable on PyPI 2026-10-12): `Scheduler(desired_retention=0.9, learning_steps=(),
  relearning_steps=(), maximum_interval=36500, enable_fuzzing=False)`,
  default parameters. Dart: a port of py-fsrs 6.3.2's Scheduler
  (`app/lib/log/fsrs6.dart`; no Dart fsrs package: `fsrs` 2.0.1 did not
  match), same settings. No fuzz, no short-term steps => deterministic replay
  on every device.
- `contract/fsrs_vectors.json` (B2, generated by
  `python -m tutor.curriculum.fsrs_vectors`; a test keeps it in step):
  `[{"name","events":[{"dev","eid","k","s","c","at","r"?,"rev"?,"reason"?}...],
  "cards":{"x":{"rev":1}},"expect":{"x":{"taught","due","stability","difficulty","state","flagged","good"}},
  "dropped":[eid...],"ignored":[eid...]}]`. Events are listed unsorted on
  purpose. `due` ms exact, floats tolerance 1e-6, `state` lowercase
  (`review`), null fields for an untaught card. Unlock never reads FSRS
  state (§6), so a divergence only shifts due dates.
- Review queue (client, offline): all subjects; taught, `due <= now`, not
  flagged, not suspended; sorted by `due`; no cap.
- Review screen: front -> reveal back + excerpt + source host (link) -> 4
  rating buttons + "Flag". Client caches derived FSRS state, rebuildable from
  the log at any time.

## 6. Unlock, mastery, daily cap (raw log only, not FSRS)
- `good(c)` iff c taught, and its **latest** review after the last `taught`
  has `r >= 3` and `at >= taught.at + 20 h` (real recall, not same sitting).
- `recall(m)` = good cards in m / (cards in m not flagged, not suspended); 0
  if empty. `mastered(m)` iff m was `ready` and `recall(m) >= 0.8`; mastery is
  sticky (a later Again does not re-lock the dependents).
- `unlocked(m)` iff plan approved and every `requires` mastered. Modules
  without requires unlock on approve. A module with a taught card is always
  unlocked (covers the migrated ones).
- Worker re-folds after every log change it sees (incremental GET every 60 s
  and before every request): writes module `status`/`recall`, starts
  generation for newly unlocked modules, sets subject `completed` when every
  module is mastered (client offers "Go deeper" / "Review only").
- **Daily new cap = 10, all subjects.** New card = a `taught` event on a card
  that was untaught at that point; `new_today` = such events with `at` on
  today's PC-local date. A
  `session_start`/`next` that would teach an untaught card when
  `new_today >= 10` -> `daily_new_cap`. Re-teaching a taught card is free.
  Client shows `stats.today.new`/`new_cap`.
- Next-card pick (worker): subject = `body.subject` or
  `prefs.current_subject`; first card in (module order, card order) that is
  untaught, not flagged/suspended, card `requires` taught, in an unlocked +
  `ready`/`mastered` module. None -> `no_card_left`. An explicit card: unknown
  -> `unknown_card`; its module not open or its requires untaught -> `locked`.
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

## 8. Client screens (parity with the retired `static/*.js` page) and their data
- **Home**: subjects with `status`/progress; "new subject" free text; due
  review count; PC presence; credited x/60; new x/10.
- **Plan**: draft view + editing (rename, reorder, add, remove module without
  cards, edit requires); comment -> `plan_revise`; Approve. Live on
  `rev.catalog`; unsaved draft edits are kept behind a "Plan changed" banner.
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

## 9. Worker API (B2 -> B1): `tutor.curriculum.handlers`
- `Context(data_dir, clock=ms, model=, fetch=, check=, device=)`; defaults are
  the real ones (device = `$TUTOR_DATA/device_id`, the crdt_sync format).
- `BUILD_HANDLERS[kind](body, ctx) -> data` for `subject_new`, `plan_revise`,
  `plan_edit`, `plan_approve`, `subject_finish`, `card_edit`. Blocking: call
  via `asyncio.to_thread`. Refusals raise `RequestError(code, message)`
  (`.result(at)` = the `result` node).
- `fold_and_advance(ctx) -> {"changed":[subj],"generate":[[subj,module]]}`
  after every log change and before each request; then
  `generate(ctx, subj, module)` per pending module on the build lane
  (`pending(ctx)` lists them again after a restart).
- `ctx.log.mirror(dev, {eid: event})` stores one device's RTDB subtree
  (idempotent, untrusted input cleaned); the worker's own `taught`/`untaught`
  events are in `ctx.log.read()` with `dev == ctx.device`, to be PUT to
  `log/{dev}/{eid}`. `stats(ctx)` builds the `stats` node.
- Engine: `Engine.start(card_id, subject=None)` (subject switch; raises
  `RequestError` `daily_new_cap`/`locked`/`unknown_card`/`no_card_left`);
  `engine.source.subject` is the live subject (a refused start keeps the
  old one); `set_card_done(card, done=, subject=)` marks any subject's card;
  `resume_latest()` resumes in the transcript's subject. Until `python -m tutor migrate`
  ran on the data dir the engine keeps the old deck + `progress.json`.
