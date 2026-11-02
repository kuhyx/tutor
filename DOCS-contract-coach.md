# Problem coach over the relay (v1, 2026-11-02)

Binding for the worker (`tutor/relay/lc*.py`) and the app (`app/lib/coach/`).
Same envelope, `chat` lane and done-map as `DOCS-contract.md` §4; the pattern
is `DOCS-contract-sql.md`. The coaching engine is `leetcode_coach`
(`~/src/utils/leetcode_coach`), the runners are `sql_drills` (MySQL and
PostgreSQL) and `code_runner` (Python 3, JavaScript, TypeScript). This file is
only the wire. Only the worker runs code, Docker or the model. Nothing here
touches the leetcode-guard gate ledger (an AST test enforces it); a solve is
still submitted on LeetCode itself.

**The id field is `lc_id`, never `session`**: the relay mirrors a body's
`session` into `sessions/<id>/meta` (busy flag, live trace). `lc_id` is 12
lowercase hex chars, minted by the worker.

| kind | body | result `data` |
|---|---|---|
| `lc_list` | `{}` | `{"recent":[Recent],"clusters":[Cluster],"due":[Due]}` |
| `lc_open` | `{"problem"?,"statement"?,"title"?,"lang"?,"lc_id"?}` | Open |
| `lc_turn` | `{"lc_id","text"<=8000,"intent"?}` | Turn |
| `lc_run` | `{"lc_id","lang","code"<=8000}` | Run |
| `lc_cards` | `{"lc_id","confirm"?:[Entry]}` | Cards |

Model-free (fast): `lc_list`, `lc_run`, `lc_turn` that is held, a gate message,
a frustration stop or a `reveal`-less refusal. Model calls (several seconds,
own isolated no-tools Claude call, the tutor's model): the other `lc_turn`s,
`lc_open` (opener), `lc_cards` (first call). The chat lane is serial: the
client shows a spinner and queues at most one of them.

## Field rules (violations are `bad_request`)
- `problem`: a leetcode.com/problems URL or a slug, <= 200 chars.
- `statement`: pasted statement markdown <= 8000 chars (the premium/unknown
  fallback; the title may come in `title` <= 120 chars). `lc_open` needs
  `problem`, `statement` or `lc_id`.
- `lang`: `mysql | postgresql | python3 | javascript | typescript`. An SQL
  problem takes only the first two, any other problem only the last three.
  `lc_open` absent = `mysql` for SQL, `python3` otherwise.
- `lc_id`: `[0-9a-f]{12}`; unknown = `bad_request`.
- `intent`: `chat` (default) | `solved`. Everything else rides in `text`:
  the bare word `hint` climbs one rung, `hint!` ("one bigger hint", the
  frustration choice) up to two; the bare word `reveal` (any case, nothing
  else, the app confirms first) is the only override; `write it` (the
  frustration choice) opens code.
- `confirm` (`lc_cards`): <= 5 `Entry` = `{"name","aliases"?:[str],"properties":[str]}`.

## Open (`lc_open`)
`problem`/`statement`: starts a session (one live coach session per device is
not enforced; the app opens one at a time). `lc_id` alone: resumes (no model
call, no heartbeat) and adds `thread`.
```json
{"lc_id":"a1b2c3d4e5f6","slug":"reformat-department-table","title":"...",
 "difficulty":"easy"|"medium"|"hard","kind":"sql"|"algo","lang":"mysql",
 "langs":["mysql","postgresql"],"statement_md":"...","starter":{"mysql":"..."},
 "model":"sonnet","retest":false,"state":State,"reply_md":"opener",
 "thread":[{"mine":bool,"md":str}]}
```
`reply_md` is the opener (restate in <= 3 sentences, ONE calibration question);
absent on resume. `thread`: the whole stored chat, oldest first, newest 120,
only on resume. The Site hints of the fetch never appear. An unreachable
LeetCode is `worker_error` + `retry:true`; premium/unknown slug is
`bad_request` with `reason:"paste_statement"`: the app shows the paste box and
sends `statement`.

`State` (also in every Turn/Run/Cards result as `state`):
```json
{"phase":"gate"|"work"|"exit"|"done",
 "gate":{"kind":"req"|"shape","tries":0,"max":3,"open":false,"forced":false},
 "turns":{"used":3,"budget":24,"over":false},"rung":"H1"|null,
 "revealed":false,"ran_ok":false,
 "exit":{"step":"explain"|"belief"|"done","tries":0,"belief":"..."?}}
```

## Gates (all in code, none in the prompt)
- **Gate message.** Until `gate.open`, text starting `req:` (algorithm
  problems: the properties the operation must have) or `shape:` (SQL: the
  output shape: columns, rows, grouping) is checked, model-free for SQL,
  by the coach library's checker for `req:`. `shape:` passes when it names
  every output column of the statement's `Output:` table (case-insensitive);
  no parseable table = `unverified` (passes). Result: `note` with the verdict
  and, when incomplete, the missing properties/columns. 3 incomplete lists open
  the gate anyway (`forced:true`, logged `req_incomplete`). A `req:` on an SQL
  problem or `shape:` on an algorithm problem is held with a note.
- **Code held back.** Until the gate is open a message that is code (a fence,
  an SQL statement, a clear assignment/call) and every `lc_run` is refused:
  `held:true`, `note` = the one-line reason, no model call, no turn counted.
  Plain chat in the gate phase is allowed (calibration).
- **Every coach reply is checked, up to 3 asks** (the reason is fed back);
  still invalid = `model_error` + `retry:true`, nothing stored:
  (1) it names a toolbox operation kuhy has not named first, before kuhy's
  first code (`leak`); (2) it writes code kuhy could paste (a fence or span
  using the problem's starter names / table and column names that is not a
  quote of kuhy's own text), before `reveal`; (3) more than one `?` outside
  code, or not ending on one question or instruction; (4) its rung is above
  the current rung + 1, above H1 for the first hint, or climbs on a message
  that is not `hint` and follows no failed run.
- **Rungs.** The model tags each reply H0-H3 (or none); the relay logs it
  (`rung` event) and `state.rung` is the highest so far. One rung per reply.
- **Reprint.** A reply that refers to "your query/code/solution" or "the
  table/output/result" without showing it gets kuhy's last snippet and/or
  last result table appended by the relay.
- **Budget.** Easy 16 / Medium 24 / Hard 32 coach turns. Past it the Turn has
  `banner:"budget"` and the reply is a <= 2-line summary plus a request for a
  full attempt. Hints and chat both count; gate messages and held turns do not.
- **Frustration.** "going in circles", a bare "stop", or two "I don't
  understand" in a row: no model call; `reply_md` owns it, `choices` is
  `["write it","hint!","reveal"]` and the app shows a 3-button sheet; the
  button sends that exact `text`.
- **Reveal.** `reveal` alone: logged, checks (1)(2) off, the reply walks the
  solution tied to the rungs seen; `state.revealed` true, phase `exit`.

## Turn (`lc_turn`)
```json
{"state":State,"reply_md":"...","note":"...","held":false,
 "banner":"budget","choices":["write it","hint!","reveal"]}
```
All but `state` optional. `reply_md` absent when the turn is a gate message or
held. `note` is a system line (gate verdict, hold reason), never from the model.

## Exit (`intent:"solved"`)
Allowed once `ran_ok` (an `lc_run` passed every example), after `reveal`, or
when a run reported `no_examples`; else held. `text` is kuhy's explanation: more than 3 sentences
is held ("say it in <= 2 sentences"). The grader (model) judges whether the key
mechanism is present; missing = `exit.missing` in the Turn plus one more turn
(3 tries, then accepted as partial). Then, if kuhy opened with a belief (the
coach tags the first stated one), `exit.step` becomes `belief` and `reply_md`
quotes it and asks what is wrong with it now; only kuhy's next `solved` text
that corrects it retires it. Finally `phase:"done"`, `exit.summary_md`: a
markdown table `step | what you showed | rung used`, built from the log by
code. Turn gains `"exit":{"ok":bool,"missing"?:str,"summary_md"?:str}`.

## Run (`lc_run`)
Runs kuhy's code on the statement's examples; the reference solution never
exists, expected values come from the statement.
```json
{"state":State,"ok":bool,"error"?:str,"no_examples":false,"passed":1,"total":2,
 "examples":[{"n":1,"ok":bool,"got"?:str,"expected"?:str,"error"?:str,
   "columns"?:[str],"rows"?:[[str]],"expected_rows"?:[[str]],
   "cell_diff"?:[[row,col,expected,actual]]}],"held"?:true,"note"?:str}
```
A user error is `ok:false` + `error` in a SUCCESSFUL request. A throw shows the
error name only. SQL runs in the dialect `lang` names (an isolated database
per run, row order ignored unless the statement orders); unparsable example
tables, design-class, list and tree problems = `no_examples:true` and a `note`
("cannot run locally", never a silent pass); `ran_ok` flips on a full pass only. Lists > 200 entries are cut with `"truncated":true`.

## Cards (`lc_cards`)
Phase must be `done`. No `confirm`: the model names which toolbox entries the
problem used and proposes properties (from the toolbox vocabulary) for an
operation the toolbox lacks. Known entries become property -> operation cards
at once; proposals are only returned. With `confirm`: each Entry is appended
to `toolbox.json` (refused with the coach's reason when it nests with an entry
or repeats a name) and its card delivered.
```json
{"state":State,"cards":[{"id":"...","front":"Toolbox: ...?","back":"name","new":bool}],
 "proposals":[Entry],"refused":[{"name":str,"reason":str}],
 "fsrs":{"added":1,"existing":0},"anki":{"delivered":bool,"line":str}}
```
Delivery is to BOTH the tutor's FSRS (subject `leetcode-toolbox`, module
`toolbox`, card id = slug of the front, so a re-run never duplicates; reviews
run in the normal review flow) and the Anki "LeetCode" deck. Anki unavailable
is `anki.delivered:false` with the reason in `line`, never a failed request.

## Lists (`lc_list`)
`Recent` `{"lc_id","slug","title","phase","updated_ms"}` (newest 20),
`Cluster` `{"name","problems":[slug]}`, `Due` `{"slug","title","due_ms"}` (a
cold re-test; the app must show "do NOT submit this on LeetCode").

## Errors and focus
Codes as `DOCS-contract.md` §4, no new ones: `bad_request` (shape, unknown
`lc_id`, wrong phase, language mismatch), `worker_error` + `retry:true`
(LeetCode, Docker, runner down or timed out), `model_error` + `retry:true`,
`claude_unavailable` (+ `reason`, `resets_at`; model kinds only). A successful
`lc_turn` or `lc_run` (also a held one) calls
`focus_project.record_activity("tutor","heartbeat")`; failures are logged,
never fail the request.

## State and log
`<data>/lc_sessions/<lc_id>.json` (survives restarts; phone and desktop share
it). The coach's session log (`~/.local/share/leetcode-coach/sessions/`) also
gets `session_start`, `req`, `req_check`, `code`, `rung`, `reveal`,
`postmortem`, `session_end`, so `leetcode report` sees app sessions.
Not in v1: `lc_predict` (predict-before-show), `lc_grade` (step grading),
the Postgres/MySQL answer-key problems, a retest start.
