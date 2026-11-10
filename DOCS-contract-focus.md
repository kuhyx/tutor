# Focus projects over the relay (v1, 2026-11-02)

Binding for the worker (`tutor/relay/focus.py`) and the app (`app/lib/focus/`).
Core rules (projects, minutes, gates) live in `~/src/utils/focus_project`;
this file is only the wire. Same envelope, lanes and done-map as
`DOCS-contract.md` §4. All five kinds are model-free and run on the `chat`
lane. Times: `ts` unix ms, dates `YYYY-MM-DD` (PC local).

| kind | body | result `data` |
|---|---|---|
| `focus_status` | `{}` | see Status |
| `focus_event` | `{"event":"start"\|"checkin"\|"stop"\|"card","ts":ms,"platform":"phone"\|"pc","subject"?,"card"?}` (`subject`+`card` only, and both required, for `card`) | `{"name","minutes","daily_minutes","unlock_minutes","ends","replaces":[...],"carry_out","unbacked_minutes"}` (fp.status of today; name null = no active project) |
| `focus_create` | `{"name"<=80,"start","end","replaces":[leetcode\|reading\|tutor],"daily_minutes":1..720,"unlock_minutes":0..daily,"subjects":[slug],"site_patterns":[host<=100 x<=20],"work_url"?:http(s) URL or ""}` | `{"id"}` |
| `focus_update` | `focus_create`'s body plus `"id"`; every field is sent again (absent lists = `[]`; absent `work_url` = kept) | `{"id","effective_from":"YYYY-MM-DD","message"?}` |
| `focus_end` | `{"id","day"?}` (day = last active day, default today; a past day is `focus_refused`) | `{}` |

Empty lists are dropped by RTDB: absent = `[]`.

`focus_update` follows focus_project's edit rules: a started project's `start`
cannot move, an ended or finished project is refused - all `focus_refused`.
An edit never lowers today's obligation (focus_project 0.7.0): a lower
`daily_minutes`/`unlock_minutes` or a gate added to `replaces` holds from
tomorrow (a mixed edit defers whole); raises, removed gates and edits to a
project that has not started hold from today. `effective_from` is the first
day the new values hold; `message` is present only when it is after today. The
frozen app ignores the response body, so it shows neither.
Floor (focus_project 0.7.1, coordinator decision): `daily_minutes` >= 30 per replaced
gate (min 30; 3 gates = 90), on create and update; below it is `focus_refused`.

## Status (`focus_status`)
`minutes` is the real count (may exceed `daily_minutes`: 121/120); `carry_out`
is the overtime banked for the next project day (max 60, `focus_project.carry`).
`unbacked_minutes` is timer time today that no same-project beat backs, so it does
not count (focus_project 0.10.0; 0 from an older package, or when nothing is
unbacked). It is always sent, in `focus_status` (active) and in the `focus_event`
reply, and is not a required status key. Beats carry the answer's own time
(`sent_at`, clamped to `[received - 48 h, received]`), so an offline answer backs
the time it was given.

```json
{"day":"2026-11-02",
 "active":{"id","name","start","end","days_left","replaces":[],"daily_minutes":120,
           "unlock_minutes":30,"subjects":[],"site_patterns":[],"work_url":"","minutes":42,"carry_out":0,"unbacked_minutes":0} | null,
 "projects":[{same as active, no "minutes"/"carry_out"/"unbacked_minutes"}],
 "gates":[{"id":"leetcode","label":"LeetCode","replaceable":true},
          {"id":"workout","label":"workout","replaceable":false}],
 "subjects":[{"id":"automation","title":"..."}]}
```
`days_left` counts today. `replaceable:false` gates are always kept (the app
shows them as "kept").

## Timer events
The client owns the timer; each tap is one `focus_event` whose `ts` is the
CLIENT time of the tap. The worker calls
`fp.record_activity("timer", event, ts=ts/1000, dev=platform)`.
A segment counts only while beats (`start`, `checkin`, or a tutor `heartbeat`,
focus_project 0.8.0) arrive <= 600 s apart; a later beat ends it at the last one.
420 s (7 min) after each beat the client asks for a check-in, leaving 180 s
before the 600 s lapse. At the lapse the client drops the prompt and,
on Android, the foreground service (native alarm at beat + 600 s; Dart may be
dead). The next tap on Start begins a new segment.

### Check-in card (2026-11-08)
At the 420 s prompt the app picks one taught card of the active project's
`subjects` from local state (most overdue first, else the soonest due) and
shows it inline on the Focus screen in place of "Still working". The pick
stays until it is rated; Stop, Start or an app restart drop it ungraded (a
reopened app picks again). Rating it writes an ordinary `review` with
`"src":"checkin"` (FSRS, done-set, no extra credit; DOCS-contract-curriculum)
and, at that same `ts`, queues:
- within 600 s of the last beat: `focus_event` `card` `{"subject","card"}`.
  The worker checks the card is a card of a subject of today's project
  (else `bad_request`) and calls
  `fp.record_activity("tutor","heartbeat",ts=ts/1000,dev=platform)`. A rating
  under 1 s after the card appeared is graded but sends nothing.
- after the lapse (the card stays, with "Missed a check-in"): `start` (a new
  segment); no `card`.
No taught card, or no `subjects`: the old "Still working?" tap, sending
`checkin`. The app sends no `checkin` while a card replaces the tap; a frozen
app's `checkin` stays valid. Notifications only open the app (web: the
Focus screen; Android: the app); they no longer check in by themselves, and
the Android "Still working" action is gone. Undo never retracts a beat.
A phone that is offline queues events locally (same rid, same `ts`, replayed
in order) and the rid is a ULID minted at tap time, so lane order = tap order.
Worker clamps: `ts` later than the request's `created` becomes `created`;
earlier than `created` - 48 h is `bad_request`.

## Errors
`focus_refused` (+`error` text): overlap with another project, bad dates,
unknown project. Not retried. Other codes as in `DOCS-contract.md` §4.

## Tutor credit
A credited tutor turn on a subject listed in the active project's `subjects`
also calls `fp.record_activity("tutor","heartbeat")` (no wire change).

# Interview projects (focus_project 0.9.0, 2026-11-10)

An `interview` project is a focus project with a test date. `focus_project`
generates its milestones (never stored, never editable) and judges them from
append-only evidence; the worker only translates. Every refusal (wrong
evidence kind for a milestone, a trip that would shrink, a `True` weekend
answer flipped to `False`, an unknown project) is a `focus_refused` result
whose `error` is focus_project's own text: show it, never swallow it. A
registry that cannot be read is `worker_error` with `retry:true`.
Milestone ids: `rules`, `trip_ask:<sat>`, `phone:<trip_start>`, `mock`, `slot`
(`<sat>`, `<trip_start>` are `YYYY-MM-DD`). States: `pending`, `done`,
`missed`, `late_done`, `unknown`; red = `missed` or `unknown`.

## `focus_create` (extended)
Same body as above plus optional `kind` (`"focus"` default | `"interview"`),
`test_at` (naive PC-local `YYYY-MM-DDTHH:MM[:SS]`), `invite_url` (http/s or
`""`), `trips` (`[{"start","end"}]` days, inclusive, <= 20) and `no_trip`
(bool). For `interview`: `test_at` is required; `end` must equal the test day;
`daily_minutes >= 30` and `unlock_minutes <= daily_minutes` are still sent (the
real targets are 30 on weekdays, 120 Sat/Sun, unlock clamped to the day);
send `trips` non-empty XOR `no_trip:true` (RTDB drops `[]`, so `no_trip` is the
explicit "none"), else `bad_request`. For `focus` the interview fields must be
absent (`bad_request`). A weekend a given trip covers is answered `true` at
creation; others are asked on their Thursday. Result `{"id"}`.

## `focus_status` (extended)
Every project row gains `kind`. An interview row also has `test_at`
(`YYYY-MM-DDTHH:MM:SS`), `invite_url`, `trips` `[{"start","end"}]` and
`weekend_answers` `{"YYYY-MM-DD": bool}`. `active` additionally has
`milestones` `[{"id","due":"YYYY-MM-DDTHH:MM:SS","state"}]` (earliest due
first) and `missed` (bool, any red; `[]`/`false` for a focus project), and for
an interview its `daily_minutes`/`unlock_minutes` are today's real targets.

## `focus_evidence`
`{"id":project,"milestone","kind","value"?,"upload"?,"chunks"?,"sha256"?,"mime"?}`

| milestone | kind | value |
|---|---|---|
| `rules` | `file` | none; the image comes via `upload` (below) |
| `phone:<trip_start>` | `tap` ("offline ok") | none |
| `mock` | `score` | number >= 0 |
| `slot` | `slot` | naive local datetime text `YYYY-MM-DDTHH:MM` |
| `slot` | `slot_confirm` ("no other duties") | `true` |

`slot` is done once a `slot_confirm` follows the latest `slot`. Result: the
milestone block after the change, `{"milestones":[...],"missed":bool,"trips":
[...],"weekend_answers":{...}}`, so the screen can redraw from it.

### `file`: the screenshot is chunked, never inline
`requests/` is mirrored whole and kept a day, so an image never rides in a
request (40 KB cap). Write base64 text chunks first:
`uploads/{ulid}/c0001 .. cNNNN` (keys zero-padded, `cNNNN` not bare numbers;
each chunk 1..262144 chars; at most 16 chunks; ULID = the upload id, e.g. a
fresh rid), then send `focus_evidence` with `upload` (that ULID), `chunks`
(count), `sha256` (lowercase hex of the decoded bytes) and `mime`
(`image/png` | `image/jpeg` | `image/webp`). The worker checks the sha256 and
the file's magic bytes against `mime` (`bad_request` otherwise; downscale a
phone screenshot to stay under ~3 MB), hands the file to focus_project, and
always deletes `uploads/{ulid}`. Write the chunks before the request.

## `focus_trip` and `focus_weekend`
- `focus_trip` `{"id","start","end"}`: announce a trip (inclusive days). It
  may only grow: a range touching an old trip must cover it, or `focus_refused`.
  The worker answers every unanswered or `false` weekend the range covers
  `true`. Result: the milestone block above.
- `focus_weekend` `{"id","saturday","trip":bool}`: answer one weekend's trip
  question (`saturday` is a Saturday inside the project before the test day).
  `true` never flips back; `false` on a weekend an announced trip covers is
  refused. Result: the milestone block above.

## Phone-prep check (worker, no request)
The `phone:*` milestone needs the offline tap plus a passing auto check. The
worker appends `phone_check` evidence `{plan, due, seen_ms}` for the active
interview project every 5 min and soon (<= 1 per minute) after any served
request, at most one row per 30 min unless the verdict inputs changed, then
runs `run_checks`. `plan` = today's plan file has a step; `due` = reviews due
over the project's `subjects`; `seen_ms` = the newest `seen` over
`presence/clients/*` with `platform:"android"` (0 + a warning when unreadable
or no phone: the check fails). **The Android app must write
`presence/clients/{dev}` = `{"platform":"android","app":v,"seen":{".sv":"timestamp"}}`
on start and resume**, else the check can never pass.
