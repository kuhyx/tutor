# Tutor contract: RTDB relay, sessions, media (v1)

Binding for B1 (relay worker, Python), B2 (curriculum engine, Python), B3
(Flutter client). Curriculum/cards/FSRS/unlock: `DOCS-contract-curriculum.md`.
Change this file first, then code. All times unix **ms** unless named `_s`.

## 1. Actors, where truth lives
- **worker**: the PC Python process (`python -m tutor worker`); headless; owns
  claude-agent-sdk, clock, ledger. One per PC.
- **client**: Flutter (Android; desktop = web build in Chrome `--app`). Never
  computes credit, never calls the model.
- **device id**: uuid4 persisted per install, never `pc`/`phone`. Worker:
  crdt_sync `load_device_identity(~/.local/share/tutor/device_id)`; Flutter:
  shared_preferences (Android) / IndexedDB (web).

| Record | Canonical | RTDB | Writer |
|---|---|---|---|
| transcripts, clock, credit | PC `sessions/<sid>.jsonl`, `ledger.json` | projection `sessions/`, `session_index/`, `stats/` | worker |
| subjects, plans, cards | PC `subjects/<subj>/` | projection `subjects/` | worker |
| reviews, flags, taught | RTDB `log/` (append-only) | canonical; worker mirrors to `log.jsonl` | each device, own subtree |
| requests | RTDB `requests/` (transient) | queue | client `req`; worker `claim`,`result` |
| prefs, archived, feedback | RTDB | canonical (feedback drained) | client |

Local jsonl write is the commit point; every RTDB projection write after it is
an idempotent re-publish. On startup the worker re-publishes any
session/subject whose RTDB `rev` < local `rev` (covers crash between the two).

## 2. Auth and transport
- DB `https://kuhy-syncs-default-rtdb.europe-west1.firebasedatabase.app`, REST
  only (no SDK), `?auth=<idToken>`. Google sign-in only.
- Worker: `FirebaseTokenProvider(api_key, credential_store_for("tutor"))` ->
  `~/.config/tutor/firebase_auth.json`, seeded by crdt-sync `tool.seed_session
  --app tutor` (see `DOCS-relay.md`). Never `firebase_client_for` nor
  `FirebaseSyncClient`: `id_token()` + own REST/SSE (`tutor/relay/rtdb.py`).
- Flutter: copy todo `lib/sync/` (`firebase_client.dart`,
  `google_sign_in_backend.dart`, google_sign_in 7.2.0). Keep the `expectedUid`
  guard (wrong Google account silently signs up a 2nd user); the expected uid
  comes from local config (`~/.config/crdt-sync/firebase.json`), never
  committed (public repo). `on Object` around sync (ArgumentError from
  `Uri.base`). "Connected" = stored session, not the account marker.
- Rules unchanged (shared DB; whole tree r/w for sync uid). No `.indexOn`
  added => only `orderBy="$key"` queries. Writer ownership below is a
  convention enforced by worker input validation.
- Conditional write: GET with header `X-Firebase-ETag: true` -> `ETag` header;
  PUT/DELETE with `if-match: <etag>`; **412** = lost race (body = current
  value, new ETag). Not available for PATCH.
- Streaming: `Accept: text/event-stream`; events `put`/`patch`
  `{"path","data"}`, `keep-alive`, `cancel`, `auth_revoked` (reconnect, fresh
  token). Every (re)connect resends the full snapshot of the path => listen
  narrowly (§9).
- Server time: `{".sv":"timestamp"}`; PUT response body has it resolved.

## 3. Layout (root `/tutor/v1`)
```
meta                    {"schema":1,"min_client":1}                    worker
rev                     {"catalog":42,"stats":7}  bumped on change     worker
presence/workers/{dev}  heartbeat (§5)                                 worker
presence/clients/{dev}  {"platform":"android","app":"1.0.0","seen":sv} client
live                    {"session":sid,"subject":"automation","card":"ld-x","since":ms} | null
requests/{rid}/req|claim|result                                        §4
sessions/{sid}/meta|msgs/{m0001}|receipts/{r0001}|user|progress        §6
session_index/{sid}     history row (§6)                               worker
subjects/{subj}/meta|plan|cards/{cid}|concepts                         curriculum doc
log/{dev}/{eid}         append-only events                             curriculum doc
prefs                   {"current_subject":"car"}                      client (LWW)
stats                   {"today":{...},"days":{"2026-10-12":{...}}}    worker
feedback/{fid}          developer report (§6)                          client; worker drains
```
IDs: `rid`,`eid`,`fid` = ULID (26 ch Crockford, device clock, sortable,
offline). `sid` = `YYYYMMDD-HHMMSS-xxxx` (unchanged, PC local). subject /
module / card ids: words of `[a-z0-9ąćęłńóśźż]` joined by `-`, NFC only, <=48 chars
(`contract/slug_vectors.json`). Message/receipt keys `m%04d`/`r%04d`, never bare
numbers (RTDB turns them into arrays). Free text (concept names) never a key: arrays
only. Client refuses to run if `meta.schema` unknown or `min_client` > own version.

## 4. Requests (relay protocol)
Client PUTs **only** `requests/{rid}/req` (a retry never clobbers claim/result):
```json
{"kind":"message","dev":"<uuid>","created":{".sv":"timestamp"},
 "sent_at":1791731346000,"body":{"session":"20261012-170448-5b71","text":"..."}}
```
`sent_at` = client time of the **first** Send press; retries keep it.

Worker streams `requests` (kept small by GC). Per rid, in key order:
1. Done-map (`requests_done.jsonl`, 30 d) has rid -> re-PUT result; no model call.
2. Claim: GET `claim` w/ ETag; claimable if null, or `lease_until` < now and no
   `result`. PUT with `if-match`:
   `{"by":"<worker dev>","lease_until":ms,"attempt":1,"phase":"claimed","at":ms}`;
   412 -> skip.
3. Lease 300 s (model turn <=240 s + image check); renew every 60 s via
   if-match PUT; `attempt` > 3 -> result `gave_up`.
4. Phases (in `claim`, mirrored to `sessions/{sid}/meta.busy`):
   `claimed -> thinking -> images -> checking_images -> publishing`. **The reply
   never streams**: image check + picture guard rewrite the draft, streaming would
   show sentences later withdrawn. The model's thinking and tool calls do: `progress` (§6).
5. Commit locally (jsonl + done-map), publish projection, then PUT `result`:
   `{"ok":true,"at":ms,"data":{...}}` or
   `{"ok":false,"at":ms,"code":"not_live","error":"session is not live","retry":false}`.
6. GC: DELETE requests whose result is >24 h old; done-map keeps dedupe.
`retry:true` (`model_error`) = resend as a NEW rid, same `sent_at`. More: `DOCS-relay.md`.

Lanes: `chat` (session kinds) and `build` (subject/plan/card kinds) are
separate serial queues; within a lane a later rid never overtakes an earlier one. For `message`, `rid` is the engine's `msg_id`.
Client: after PUT, follow `requests/{rid}` until `result`, show phase (one
`requests` listen ranged `orderBy="$key"&startAt="<oldest followed rid>"`
serves every request in flight, §9). On
network error re-PUT the same `req` (same rid, same `sent_at`), never a new
rid. Requests may queue while the PC is offline; served when it is back.

Error codes (extra fields flat in the result node, `DOCS-relay.md`): `bad_request` (unknown kind, bad id, oversize), `not_live`, `session_live` (stop the live session first), `locked` (+`subject_title`, `next`: `review_module` +`module`, `module_title` | `none`),
`daily_new_cap` (+`subject_title`, `new_today`, `new_cap`, `module`, `module_title`, `due_in_subject`, `next: "lift_cap"`), `no_card_left` (+`subject_title`, `due_in_subject`, `next`: `review_module` +`module`, `module_title` | `reviews_due` +`due_at` ms | `none`), `unknown_card`, `plan_conflict`, `edit_refused`, `model_error`, `claude_unavailable` (+`reason`, `resets_at`), `unknown_prompt`, `gave_up`,
`worker_error` (`DOCS-relay.md`). `error` is shown, except for `locked`/`daily_new_cap`/`no_card_left`: the app builds a call to action from the fields (a `next: lift_cap` = "Learn more anyway"). Tracebacks stay in the log.

| kind | body | result `data` | lane |
|---|---|---|---|
| `subject_new` | `{"text":"I want to learn how a car works"}` <=2000 ch | `{"subject":"car"}` (plan drafted) | build |
| `plan_revise` | `{"subject","plan_rev":3,"comment":"less history"}` | `{"plan_rev":4}` | build |
| `plan_edit` | `{"subject","plan_rev":3,"modules":[module...]}` | `{"plan_rev":4}` | build |
| `plan_approve` | `{"subject","plan_rev":4}` | `{}` | build |
| `subject_finish` | `{"subject","choice":"go_deeper"\|"review_only"}` | `{"plan_rev":5}` or `{}` | build |
| `module_pregenerate` | `{"subject","modules":["b",...]\|"all"}` draft locked modules' cards ahead; study still waits for `requires` (curriculum §2) | `{"queued":["b"]}` | build |
| `card_edit` | `{"subject","card":"ld-x"\|null,"module","front","back","source","excerpt","requires":[]}`; also `card_restore` / `card_remove` `{"subject","card"}`: the Editor's Restore of a tutor- or Editor-removed card (puts its `requires` back; an older unrecorded Editor removal is only un-suspended) and Remove of a tutor-added one (curriculum §3) | `{"card":"ld-x","rev":2}` (undo: `{"card"}`) | build |
| `session_start` | `{"subject":"car"\|null,"card":"..."\|null,"resume":bool?,"device"?,"lift_cap":bool?}` (null card = next open; `device` as for `message`, shapes the opening turn; `lift_cap:true` = "Learn more anyway": first lifts today's daily new cap on every device, a worker `cap_lift` event written once per day, curriculum §6) | `{"session":sid}` | chat |
| `session_resume` | `{"session":sid,"device"?}` (device validated only: no model turn) | `{"session":sid}` | chat |
| `message` | `{"session":sid,"text":"...","device":"phone"\|"desktop"?}` <=8000 ch; no device = desktop, other values `bad_request`; phone: typos ignored, short answers, one question (prompt rule 13); text `Hint` gets a hint, never credit | `{"msg":"m0012"}` | chat |
| `next` | `{"session":sid,"device"?}` (next_card+stop, starts new on `device`) | `{"session":newsid}` | chat |
| `stop` | `{"session":sid}` | `{}` | chat |
| `follow_up_open` | `{"session":sid}` reopen a session whose card was done there, for follow-up questions (`DOCS-relay.md` "Follow-ups"); another live session -> `session_live` | `{"session":sid}` | chat |
| `card_done` | `{"subject","card","done":true}` manual override | `{}` | chat |
| `drill_next`, `drill_answer` | the model-free drill, `DOCS-relay.md` "Claude unavailable" | | chat |
| `anki_status` | `{}` (credits new Anki reviews first; idempotent) | `{"credited_today_min","eligible_today_min","last_sync_at":s\|null,"unavailable":{"until":s,"reason"}\|null}` | chat |

One live session at a time; message for a non-`live` session -> `not_live`,
client offers Continue (`session_resume`, replaces `resume_latest`, re-primes
from transcript; previously live session is not stopped). `advance_s` never
on the wire (worker CLI only). History "Repeat" = `session_start` with that
card. Home Continue = `resume:true`: the subject's live session, else its newest session if unstopped with its card untaught (or taught there), else next open card.

## 5. Presence
- Worker every 30 s PUTs `presence/workers/{dev}` (each beat measures skew):
  `{"host","pid","version","started":ms,"beat":{".sv":"timestamp"},"lanes":{"chat":rid|null,"build":rid|null},"skew_ms":12}`;
  DELETE on clean exit.
- Client streams `presence/workers` while foregrounded; "PC offline" when no
  put/patch for **75 s** on the client's **monotonic** clock (never compare
  `beat` with device wall clock). Connect snapshot = "checking" until next beat.
- Offline: chat/plan/subject actions show "PC offline: replies wait; reviews
  still work". Reviews and flags keep working.

## 6. Session projection (worker-written except `user`)
```json
"meta": {"subject":"automation","card":{"id":"ld-x","front":"..."},"started":ms,
  "stopped":false,"card_done":false,"check_open":true,"n":14,"rev":31,
  "clock":{"active_seconds":412.5,"paused_reason":null,"awaiting_since":ms,"reply_timeout_s":600},
  "credited_minutes":6,
  "busy":{"rid":"...","phase":"thinking","since":ms,"text":"pending learner text"}}
"msgs/m0007": {"role":"tutor","text":"markdown","questions":["...","..."],"choices":[[],["a","b","c"]],"low_effort":false,
  "check":{"question":"...","concept":"...","choices":["a","b","c"]},"check_result":{"passed":true,"feedback":"..."},
  "images":[IMG],"diagrams":[DGM],"mastered_new":["..."],"notices":["Card removed: <front>"],"card_done":false,"at":ms,"trace":[STEP]}
"msgs/m0008": {"role":"learner","text":"...","at":ms,"rid":"...","dev":"..."}
"msgs/m0009": {"role":"card","text":"<front>","card_id":"ld-y"}
"receipts/r0003": {"entry_id":"<sid>-m6","recorded":true,"minutes":1,"minutes_today":23,"error":null,"at":ms}
"user": {"archived":true}, "progress": {"rid":"...","steps":{"s0001":STEP,"s0002":STEP}}
```
- `busy` null when idle; `check`/`check_result` may be null. `user` is
  client-written; the live session can't be archived. `choices[i]` belongs to `questions[i]`, `check.choices` to the check: `[]` or 3 short answers (one right, unmarked). RTDB drops empty lists, so a client reads a missing `choices`, a missing index or null as `[]` (old transcripts have none). A box still holding a tapped choice, unedited, is sent as `A: <choice> (picked option)`; a tapped check answer never passes on its own (`tutor/picked.py`): the server takes back any pass, mastery and `card_done`, and a typed one-sentence why (check `choices` `[]`) is what passes.
- `STEP` = `{"kind":"thinking","text"}` | `{"kind":"tool","name":"WebSearch","input":"<query/url/command, <=150 ch>"}`: the model's summarized thinking and research, in order; adjacent thinking steps concatenate. `trace` = the final list (thinking <=8000 ch, <=30 tools; absent when empty), stored with the turn (`ui.trace` in `sessions/<sid>.jsonl`); display only, never in the resume primer or any prompt. `progress` (worker): PUT on a request's first flush, then PATCH `progress/steps` with only the new keys, at most every 0.5 s (desktop request) / 2 s (`device: phone`); DELETEd with `busy`; clients show it only while `meta.busy.rid == progress.rid`.
- Learner bubble appears only after the turn succeeds (as today); until then
  all devices show `busy.text` as a pending bubble. "Stalled" =
  `awaiting_since + 600 s < now` (client display only).
- `session_index/{sid}`: `{"started":"2026-10-12 17:04","subject":"automation","cards":[{"id","front","done","done_here"}],"active_minutes":12,"credited_minutes":12,"stopped":true,"auto_archived":false,"rev":31}`.
- `feedback/{fid}`: `{"category":"ui|response|experience|other","text":"<=4000","session":sid|null,"msg":"m0007"|null,"dev","at":ms,"route":"/session"}`;
  worker attaches its message snapshot, appends `feedback.jsonl`, DELETEs the
  node. Feedback never reaches the model.

## 7. Credit honesty (worker only)
- Clock = existing `EngagementClock`, replayed only from local jsonl.
- Learner time `t_l = reply_time(received=req.created/1000, sent_at=req.sent_at/1000)`:
  `created` is RTDB server time, never the phone clock; `sent_at` can only move
  it up to `SEND_GRACE` = 300 s earlier; a value later than `created` ignored.
- Tutor time `t_t` = worker `time.time()` at final message commit.
- Worker measures skew (`.sv` write vs local) at startup + hourly; |skew| > 5 s
  warns and shows `skew_ms` in presence.
- Learner events logged with `t`,`rid`,`dev`. Ledger rows signed exactly as
  today (credit.py, earner `TUTOR`, `entry_id <sid>-m<n>`, cap 60/day,
  `confirmed_on` unset). RTDB `receipts`/`stats` are display only; earned_time
  never reads RTDB.
- An answer delayed by an offline phone earns only what `REPLY_TIMEOUT`
  (600 s) allows from server receipt. A device cannot claim minutes. A restart reopens the window (<= 1 h) only for an on-time reply still in flight; idle time across it earns nothing.
- FSRS reviews earn no credit in v1; the drill credits active minutes only.

## 8. Media (no Firebase Storage, nothing binary in RTDB)
- `IMG` = `{"url":"https://upload.wikimedia.org/...800px-....jpg","title","author","licence","licence_url","page_url","term"}`.
  Worker still downloads the thumbnail for the vision check but publishes the
  `thumburl` (`iiurlwidth=800`, query stripped; Commons also serves it from
  `thumb.wikimedia.org`, 960 px), `url` absent if unresolvable. `author`/
  `licence` plain text. Client loads only `upload.`/`thumb.wikimedia.org`,
  shows "author · licence" linked to `page_url` under every picture, uses the
  HTTP cache; on load failure shows attribution + link only. B3 verifies
  hotlinking on device (descriptive User-Agent).
- `DGM` = `{"title","svg":"<svg ...>"}` inline, <=8 KB, <=2 per message;
  schemdraw output from the closed element set only, never model markup.
  Worker asserts no `<script>`, `<foreignObject>`, external `href`. Client
  renders with flutter_svg.

## 9. Budgets (Spark: 10 GB/mo download, 1 GB stored, 100 conns, shared)
Tutor target <=1 GB/month download, <=50 MB stored. Caps: message 8000 ch;
tutor message <=24 KB incl. SVG (`trace` has its own caps, §6); card <=2 KB; plan <=16 KB; feedback 4000 ch.
Client streams only while visible: `live`, `presence/workers`, `rev`,
`sessions/{sid}` (one listen: meta, msgs, progress), `requests` ranged from
the oldest rid in flight; never the `/tutor/v1`, `sessions`, `subjects` or
`log` roots. **At most 4 streams at once** (2026-10-20): RTDB answers over
HTTP/1.1 only, a browser holds 6 connections per host and every stream keeps
one, so a 6th stream left a Send's PUT no socket. `rev` closes while a
request is followed (its reopening snapshot emits any move meanwhile), so a
Session holds `presence/workers`, `live`, `sessions/{sid}` and `rev` or
`requests`; `app/test/ui/stream_budget_test.dart` counts them per screen
state. Reconnect cost: the whole session, msgs ~30 x 2 KB = 60 KB + meta
~1 KB + progress append-only <=~12 KB/turn (the per-msgs `startAt` resume,
verified 2026-10-12 to work on SSE, is given up for the connection);
presence ~0.3 KB.
Catalog: GET `subjects/{s}` only on a `rev.catalog` move (167 PLC cards ~90 KB
once); `rev` = ONE shared listen, closed while hidden; Plan/Editor refetch per
move, Home only on top. Log: GET `log/{dev}?orderBy="$key"&startAt="<last eid>"`
per device (shallow first), ~150 B/event. 1 h chat/day ~2-5 MB/device/day, <0.2 GB/month.

## 10. Security
- Public repo: no uid, email, API key or tokens in source/docs; config from
  `~/.config`. Scan history before the first push.
- All RTDB content is untrusted: worker validates kind, id regexes, types,
  sizes; ignores unknown fields; never builds a path/filename from an
  unvalidated id.
- No MCP, settings or hooks for any model; tools only for the tutor, in
  bubblewrap (`research.py`), else `isolated_options`; `wrap_learner`.
- Client: markdown with raw HTML off; https links only; image host allowlist;
  SVG only from worker.
- Credit unforgeable via RTDB: root-owned HMAC key stays on the PC; time
  inputs server-stamped.
- Tokens: Android keystore; `~/.config/tutor/` on PC. Transcripts/reviews in
  Google RTDB are personal, not secret.

## 11. Migration
The one-off A2/B migration (`python -m tutor migrate`): `DOCS-migration.md`.
