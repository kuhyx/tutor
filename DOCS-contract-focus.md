# Focus projects over the relay (v1, 2026-11-02)

Binding for the worker (`tutor/relay/focus.py`) and the app (`app/lib/focus/`).
Core rules (projects, minutes, gates) live in `~/src/utils/focus_project`;
this file is only the wire. Same envelope, lanes and done-map as
`DOCS-contract.md` §4. All five kinds are model-free and run on the `chat`
lane. Times: `ts` unix ms, dates `YYYY-MM-DD` (PC local).

| kind | body | result `data` |
|---|---|---|
| `focus_status` | `{}` | see Status |
| `focus_event` | `{"event":"start"\|"checkin"\|"stop","ts":ms,"platform":"phone"\|"pc"}` | `{"name","minutes","daily_minutes","unlock_minutes","ends","replaces":[...],"carry_out"}` (fp.status of today; name null = no active project) |
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

## Status (`focus_status`)
`minutes` is the real count (may exceed `daily_minutes`: 121/120); `carry_out`
is the overtime banked for the next project day (max 60, `focus_project.carry`).

```json
{"day":"2026-11-02",
 "active":{"id","name","start","end","days_left","replaces":[],"daily_minutes":120,
           "unlock_minutes":30,"subjects":[],"site_patterns":[],"work_url":"","minutes":42,"carry_out":0} | null,
 "projects":[{same as active, no "minutes"/"carry_out"}],
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
A segment counts only while check-ins arrive <= 600 s apart (focus_project).
The client asks "Still working?" 420 s (7 min) after each tap, leaving 180 s to
answer before the 600 s lapse. At the lapse the client drops the prompt and,
on Android, the foreground service (native alarm at tap + 600 s; Dart may be
dead). The next tap on Start begins a new segment.
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
