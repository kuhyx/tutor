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

Model-free (fast, ~100 ms warm): `sql_list`, `sql_get`, `sql_run`,
`sql_predict`. Model calls (several seconds, own isolated Claude call, no
tools): `sql_hint`, `sql_generate`. The chat lane is serial: a hint or a
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
"match":bool,"cell_diff":[[row,col,expected,actual]],"extra":[...],"missing":[...]}`.
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
It must return ONE short Socratic question (<= 400 chars, one `?`, at the end,
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
