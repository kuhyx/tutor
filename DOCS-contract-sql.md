# SQL practice over the relay (v1, 2026-11-02)

Binding for the worker (`tutor/relay/sql.py`, `sql_protocol.py`) and the app
(`app/lib/sql/`). The engine (MySQL 8.0.33 in Docker, HackerRank-style exact
match, drill store) is `~/src/utils/sql_drills` (`import sql_drills as sd`);
this file is only the wire. Same envelope, `chat` lane and done-map as
`DOCS-contract.md` §4. Only the worker touches Docker. The reference SQL of a
drill never appears on the wire.

| kind | body | result `data` |
|---|---|---|
| `sql_list` | `{}` | `{"drills":[DrillMeta],"topics":[str]}` |
| `sql_get` | `{"id"}` | Drill |
| `sql_run` | `{"id","sql"<=8000}` | RunResult |
| `sql_predict` | `{"id","grid":[[str]]}` | PredResult |
| `sql_hint` | `{"id","sql"?,"last_result"?,"history"?}` | `{"question"}` |
| `sql_generate` | `{"topic","difficulty"?}` | DrillMeta |
| `sql_lesson_turn` | `{"topic","lesson_id"?,"answer"?}` | Lesson turn |

Model-free (fast, ~100 ms warm): `sql_list`, `sql_get`, `sql_run`,
`sql_predict`. Model calls (several seconds, own isolated Claude call, no
tools): `sql_hint`, `sql_generate`, `sql_lesson_turn` (an answered turn takes 10-40 s:
two model calls at most). The chat lane is serial: a hint or a
generate holds up other chat requests while it runs, so the client shows a
spinner and does not queue more than one of either.

## Field rules (violations are `bad_request`)
- `id`: `[A-Za-z0-9_.-]{1,64}`; an id the engine does not know is `bad_request`
  (`unknown drill`).
- `sql`: non-empty string <= 8000 chars (`sql_hint`: may be absent or `""`).
- `grid`: <= 60 rows of <= 30 cells, each cell a string <= 200 chars. One row =
  one result row, cell order = the query's column order. Absent = `[]` (the
  user predicts "no rows"; RTDB drops empty lists).
- `history` (`sql_hint`): the hint questions already shown for this drill,
  oldest first, <= 10 strings of <= 500 chars; absent = `[]`.
- `last_result` (`sql_hint`): the last `sql_run` data object, or absent. Only
  `ok`, `error`, `columns`, `match`, the first 20 `rows` and the first 20
  `cell_diff` entries are read; the rest is dropped.
- `topic`: one of `basics`, `pivot`, `dates`, `number-format`, `joins-null`,
  `group-having`, `window`, `strings`. `difficulty`: `easy|medium|hard`,
  absent = `medium`.

## Shapes
`DrillMeta`:
`{"id","title","topic","kind":"write"|"predict","source":"builtin"|"generated"}`

`Drill` (`sql_get`):
`{"meta":DrillMeta,"task_md","schema_sql","tables":{name:{"columns":[str],"rows":[[str]]}},
"expected_preview":[[str]],"query":str}`. `write` drills carry
`expected_preview` (first rows of the expected output); `predict` drills carry
`query` (the SQL whose output the user types into the grid).

`RunResult` (`sql_run`):
`{"ok":bool,"error"?:str,"columns":[str],"rows":[[str]],"expected_rows":[[str]],
"match":bool,"cell_diff":[[row,col,expected,actual]],"extra_rows":[[str]],"missing_rows":[[str]]}`.
A user SQL error is `ok:false` + `error` (MySQL's text) in a SUCCESSFUL
request, never a failed one. `row`/`col` are 0-based. Cells are the
normalised strings the judge compares (NULL = `NULL`, tabs -> space); a cell
that exists on one side only is `""` on the other (RTDB drops nulls inside
arrays, so the wire never carries one).

`PredResult` (`sql_predict`): `{"match":bool,"cell_diff":[...],"actual_rows":[[str]]}`.

RTDB drops empty lists and nulls: an absent list is `[]`, an absent `error` is
none. Lists longer than 200 entries (`cell_diff`: 500) are cut and
`"truncated":true` is added (also on a table whose rows were cut).

## Hints (`sql_hint`)
The model gets the task, the schema, the user's `sql`, the compact
`last_result` and the earlier hint questions; it never gets the reference SQL.
Hints graduate with the number of earlier hints in `history`: level 1 only
points at the rule, table or column and names no function or syntax (the
worker rejects and re-asks one that does), level 2 names the concept, from
level 3 a function may be named. It must return ONE short Socratic question (<= 400 chars, one `?`, at the end,
no code fence, no SQL statement). The worker validates this and re-asks up to
2 times; still invalid = `model_error` (`retry:true`). A hint that would hand
over the answer is therefore never delivered.

## Generated drills (`sql_generate`)
The model returns `{title,topic,task_md,schema_sql,reference_sql}` (generic
wording, no company names); `sd.save_generated` runs the reference on a fresh
database and rejects an empty or erroring one. Up to 2 retries with the
rejection text; then `model_error` (`retry:true`). The returned meta's `topic`
is always the requested one. The drill then shows in `sql_list`
(`source:"generated"`).

## Errors
Codes as in `DOCS-contract.md` §4; no new ones. `bad_request` (shape, unknown
id), `worker_error` + `retry:true` (Docker/engine down or timed out; the
worker starts the container itself first), `model_error` +
`retry:true`, `claude_unavailable` (+ `reason`, `resets_at`; hint and generate
only). `error` is text for the user.

## Focus
A successful `sql_run` or `sql_predict` calls
`focus_project.record_activity("sql_drills","heartbeat")` (no wire change;
failures are logged, never fail the request).

## Guided lesson (`sql_lesson_turn`)
A Socratic lesson per topic, driven by the tutor's model with the engine as
ground truth: every result the learner is asked about is the REAL output of a
query run by `sql_drills` on the lesson's dataset (a builtin drill's tables);
the model never writes result rows. It asks ONE question at a time ("what does
this return, and why, in one sentence"), grades prediction AND reasoning (a
right list with a wrong reason is probed, not passed), probes a wrong model
with a variant query / plain-language reframe / "fill the unknown both ways",
confirms only once the learner states the rule, then shows a summary table
and asks 2 mini-checks before the next concept.

Body: `topic` (as `sql_generate`), `lesson_id`? (absent = start a new lesson;
the worker mints it), `answer`? (free text <= 2000 chars, non-blank).
- no `lesson_id`: starts a lesson; `answer` must be absent (`bad_request`).
- `lesson_id` + `answer`: grades the pending question, returns the next turn.
  Counts as focus activity (heartbeat).
- `lesson_id` without `answer`: returns the current turn again (resume; no
  model call, no heartbeat) plus `thread`: the whole stored conversation,
  oldest first, `[{"mine":bool,"md":str}|{"mine":false,"grid":{columns,rows}}]`
  (newest 120 entries). The app replaces its chat with it. Unknown id or
  another topic = `bad_request`.
- The learner never scrolls: a question that refers to an earlier query
  ("rewrite Q6") must restate its SQL inline; the worker rejects and re-asks
  a turn that points back without it.
State lives on the worker (`<data>/sql_lessons/<lesson_id>.json`), so a lesson
survives app restarts and works from phone and desktop alike.

Concepts per topic (order = progression): `basics`: NULL comparisons, JOIN ON
vs WHERE; `joins-null`: anti-join; `group-having`: HAVING; `pivot`; `dates`;
`number-format`; `window`; `strings`. The app walks the topics in that order.

Result `data`:
```json
{"lesson_id":"a1b2c3d4e5f6","topic":"basics","turn":3,
 "progress":{"concept":"NULL comparisons","index":0,"total":2,
             "phase":"teach"|"check","checks_left":0..2},
 "question_md":"...","tables":{"customers":{"columns":[],"rows":[[]]}},
 "feedback_md":"...","summary_md":"...","result":{"columns":[],"rows":[[]]},
 "done":true}
```
- `question_md`: the current question, with its query in a code fence. Absent
  when `done`. `tables`: the CURRENT dataset, every turn (pin it above the
  question; it changes when the concept changes).
- `feedback_md`: reaction to the last answer (absent on the first turn). It
  never states the answer or the rule before the learner has.
- `summary_md`: a compact summary table, sent once when a concept is mastered
  (never repeated; the last concept's `done` turn carries only `feedback_md`).
- `result`: the real output of the PREVIOUS question's query; present only
  when the learner's answer was fully right (prediction and reasoning).
- `done:true`: the topic's last concept is finished; no further turn.
- `phase:"check"`: the question is a mini-check; two right in a row advance;
  a wrong one returns to `teach`.
Errors: as the other model kinds (`model_error` + `retry:true` when the model
could not produce a valid turn in 3 tries; the stored state is unchanged, so
the same `answer` may be sent again with a new rid).

### Cards from lessons (2026-11-02)
When a concept is mastered (the turn that carries `summary_md`) the worker adds
that concept's cards to the MySQL subject (`mysql-8-for-timed-sql-coding-tests-joins-and`,
module `sql-lessons`, `ready`, no `requires`) and `taught`s them now, so FSRS
schedules the first review. Cards live in `tutor/curriculum/sql_bank*.py`
(concept title -> cards): each back shows the REAL MySQL result of its
example query (run by `sql_drills`), each excerpt is checked against its
source as for any card. Ids are `sql-<key>`; an existing id is never changed,
a taught card is never taught twice, a suspended one stays suspended. A
failure is logged and never fails the turn; the next mastery retries.
Taught cards count toward the daily new cap. Backfill / repair:
`python -m tutor sql-cards [--data DIR] [--taught-days-ago N]`.
