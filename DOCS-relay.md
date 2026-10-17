# The RTDB relay worker (`tutor/relay/`)

How the PC side of `DOCS-contract.md` is built. The contract wins on any
conflict; this file holds the worker-only details.

## Running it
- In the web server (transition): `TUTOR_RELAY=1` or `--relay`. The live
  server, `tutor.service` (`systemd/tutor.service`), sets it (a drop-in with
  `Environment=TUTOR_RELAY=0` turns it off); the deploy smoke test always runs
  with `TUTOR_RELAY=0`, so a temp-data server never claims real phone requests.
  The unit's `ExecStartPre` (`scripts/tutor_port_free.sh`) refuses a second
  server on :8778: the relay starts before the port is bound. No session in
  `~/.config/tutor/` -> the relay logs why and only the web app is served.
- Headless: `python -m tutor worker` (same startup as the server: repair,
  backfill, resume; SIGTERM drains). One Engine either way.
- Migration (after `python -m tutor migrate`): `python -m tutor publish-all`
  publishes every transcript, every subject, the worker's own log events and the
  archived flags of `progress.json`.
- The live release runs on the repo `.venv`: after pulling this, run
  `scripts/setup_dev.sh` (crdt-sync + httpx); the deploy refuses otherwise.

## Credential
`~/.config/tutor/firebase_auth.json` (0600). The real seeder,
`python3 -m tool.seed_session --client-id ... --client-secret ... --app tutor`
(in `~/src/utils/crdt-sync`), needs one interactive Google consent;
`link_google.py` only links an account and cannot seed. Interim (2026-10-12):
a copy of the `firebase_backup` app's session of the same account. Run the
seeder once to give the tutor its own refresh token.

## Modules
- `rtdb.py` REST (httpx; `?auth=` never logged), `sse.py` streams with
  reconnect (`auth_revoked` -> fresh token, errors back off 1-30 s, `cancel`
  fatal), `mirror.py` local copy of a streamed node.
- `inbox.py` watches `requests`, queues per lane, rescans every 60 s, GCs
  results older than 24 h. `lanes.py` serves one rid: done-map, claim,
  validate (`protocol.py`), handler, commit, publish, `result`.
- `claims.py` is the only writer of `requests/{rid}/claim` (holds the ETag;
  renews every 60 s; mirrors phases to `sessions/{sid}/meta/busy`).
  `busy` always clears: `serve()` clears it in a `finally` (bugs, cancels),
  a failed clear joins `Server.stale_busy`, and `sweep_busy()` retries it
  whenever no request is in flight (startup seeds the live session, then
  every refresh).
  `phases.py` reports `thinking`/`images`/`checking_images` from the
  engine's model session (an injected session factory, no engine hooks).
- `chat.py` the session kinds; `projection.py` + `views.py` +
  `media_out.py` the published nodes; `presence.py`, `feedback_drain.py`,
  `stats.py` (minimal until `tutor.curriculum.stats.build(engine)` exists).

## Rules the code follows
- Own dead claims: a claim whose `by` is this worker's device id but which is
  not in flight here is a dead process's (one worker per device) and is taken
  over at once instead of after the 300 s lease.
- `result.at` is server time. Invalid rid keys (not a ULID) get no result.
- Done-map rows are written before the projection and the result PUT; a rid
  found there is answered again and never re-run (no second model call).
- `rev` of a session = its transcript's event count; startup re-publishes
  every session whose `session_index/{sid}/rev` is lower.
- HTTP turns (`tutor.scripted` runs) are picked up by a 30 s refresh of the live
  session.

## Curriculum (`tutor.curriculum.handlers`, `DOCS-contract-curriculum.md` §9)
- Build kinds: `BUILD_HANDLERS[kind](body, engine.ctx)` in a thread
  (`hooks.py`), under the build lock. Their `RequestError` (`.code`,
  `.message`) becomes the error result.
- `curriculum_sync.py`, before and after every request and every minute:
  pull other devices' `log/{dev}` (`orderBy="$key"&startAt=<newest seen>`)
  into `ctx.log.mirror`, `fold_and_advance`, publish each subject whose local
  `meta.rev` moved (`subjects/{s}/plan|cards|concepts|meta`, only changed
  parts; `rev.catalog` + 1), PATCH own `taught`/`untaught` events to
  `log/{worker}`, queue `generate` pairs. One generation at a time, under the
  build lock; a module whose generation raised is not retried until restart.
- `no_card_left` (`session_start` / `next` with no open card) also carries
  `subject_title` and `next`: `review_module` (+`module` id, `module_title`:
  the first `ready` module fully taught, not yet reviewed), else
  `reviews_due` (+`due_at` ms: earliest FSRS due of a taught, unflagged,
  unsuspended card), else `none`. `error` = the subject's title (never the
  slug) + that step, e.g. `Hosting WWW — all cards of “DNS i CNAME” are
  taught. Review them to open the next module.`
- Stats node: `handlers.stats(engine.ctx)`. `session_start` / `card_done` pass
  `subject`; `live.subject` = `engine.source.subject`.

## Claude unavailable and the drill (`tutor.outage`, `tutor.drill`)
- An outage is read from typed SDK fields, never prose: a `RateLimitEvent`
  with `status` `rejected` (its `resets_at`), an API error's HTTP status (429
  `rate_limit`, any 5xx `overloaded`), or `AssistantMessage.error`
  `server_error` / `terminal_reason` `api_error` with no status (`network`).
  A turn that answered is never one. Overloaded / network are retried once in
  `TutorSession`; what still fails is appended to `unavailable.jsonl`.
- Result `{"ok":false,"code":"claude_unavailable","retry":false,"reason",
  "resets_at":<unix s, the window's end>,"error"}`; HTTP `/api/*` answers the
  same fields with 503. While a window covers `now`, `session_start`,
  `session_resume`, `message` and `next` fail fast with it (no CLI spawned).
- `drill_next` `{"subject":slug|null}` -> `{"prompt_id":ulid,"card":{"subject",
  "id","front"},"options":[str x<=4],"today":{"active_min","credited_min"},
  "unavailable":{"until","reason"}|null}`, or `{"empty":true}` with no taught
  card. Taught = the fold's, plus `progress.json` `cards_done` for
  `automation`; oldest due first; distractors are other backs of the topic,
  then the subject, ordered by a hash of the prompt id.
- `drill_answer` `{"prompt_id":ulid,"choice":int}` -> `{"correct",
  "answer_index","back","excerpt","source","minute_credited","today"}`. One
  prompt is open; answered, replaced or lost on restart -> `unknown_prompt`.
  A pick appends one `review` (`r` 3 / 1, `rev`, `dur_ms`, `"src":"drill"`,
  the worker's dev) that the sync pushes to `log/{worker}`. It schedules
  (FSRS) and feeds `good` but never makes a card `reviewed` (curriculum §6). Shown -> pick is a learner gap on
  the tutor's clock (right or wrong, within `REPLY_TIMEOUT`, none under 3 s);
  minutes go through `credit_units` as session `drill-<id>` (one per day),
  daily cap only. Its log: `drill/<session>.jsonl`, not `sessions/`.

## Live check (2026-10-12, scratch data dir, real RTDB)
`session_start` claimed in 0.24 s, result in 4.99 s; `message` "hello" result
in 3.29 s; a picture turn went claimed -> thinking -> images ->
checking_images -> publishing (12.9 s). Learner time = `sent_at` (inside
grace of `created`). `bad_request` / `not_live` codes as specified; feedback
drained to `feedback.jsonl`; presence beat (skew 25 ms) and deleted on clean
exit. SSE with `orderBy="$key"&startAt=` returns only keys >= startAt.

## Client: a reply that never lands
The session screen's runner is stalled after 3 min with no result and no new
phase: the line reads "No reply from PC — send again" and Send, Ctrl+Enter and
Hint reopen (typed text is kept). The same text again re-PUTs the same rid, so
a late result lands once (done-map, no second model call); other text is a new
message under a new rid.
