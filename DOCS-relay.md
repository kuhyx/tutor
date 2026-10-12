# The RTDB relay worker (`tutor/relay/`)

How the PC side of `DOCS-contract.md` is built. The contract wins on any
conflict; this file holds the worker-only details.

## Running it
- In the web server (transition): `TUTOR_RELAY=1` or `--relay`. `run.sh` and
  `scripts/tutor_deploy.sh` set it for the live server (`TUTOR_RELAY=0` turns
  it off); the deploy smoke test always runs with `TUTOR_RELAY=0`, so a
  temp-data server never claims real phone requests. No session in
  `~/.config/tutor/` -> the relay logs why and the page is served alone.
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
- Web-page turns are picked up by a 30 s refresh of the live session.

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
- Stats node: `handlers.stats(engine.ctx)`. `session_start` / `card_done` pass
  `subject`; `live.subject` = `engine.source.subject`.

## Live check (2026-10-12, scratch data dir, real RTDB)
`session_start` claimed in 0.24 s, result in 4.99 s; `message` "hello" result
in 3.29 s; a picture turn went claimed -> thinking -> images ->
checking_images -> publishing (12.9 s). Learner time = `sent_at` (inside
grace of `created`). `bad_request` / `not_live` codes as specified; feedback
drained to `feedback.jsonl`; presence beat (skew 25 ms) and deleted on clean
exit. SSE with `orderBy="$key"&startAt=` returns only keys >= startAt.
