# Focus projects over the relay (v1, 2026-11-02)

Binding for the worker (`tutor/relay/focus.py`) and the app (`app/lib/focus/`).
Core rules (projects, minutes, gates) live in `~/src/utils/focus_project`;
this file is only the wire. Same envelope, lanes and done-map as
`DOCS-contract.md` §4. All four kinds are model-free and run on the `chat`
lane. Times: `ts` unix ms, dates `YYYY-MM-DD` (PC local).

| kind | body | result `data` |
|---|---|---|
| `focus_status` | `{}` | see Status |
| `focus_event` | `{"event":"start"\|"checkin"\|"stop","ts":ms,"platform":"phone"\|"pc"}` | `{"name","minutes","daily_minutes","unlock_minutes","ends","replaces":[...]}` (fp.status of today; name null = no active project) |
| `focus_create` | `{"name"<=80,"start","end","replaces":[leetcode\|reading\|tutor],"daily_minutes":1..720,"unlock_minutes":0..daily,"subjects":[slug],"site_patterns":[host<=100 x<=20]}` | `{"id"}` |
| `focus_end` | `{"id","day"?}` (day = last active day, default today) | `{}` |

Empty lists are dropped by RTDB: absent = `[]`.

## Status (`focus_status`)
```json
{"day":"2026-11-02",
 "active":{"id","name","start","end","days_left","replaces":[],"daily_minutes":120,
           "unlock_minutes":30,"subjects":[],"site_patterns":[],"minutes":42} | null,
 "projects":[{same as active, no "minutes"}],
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
