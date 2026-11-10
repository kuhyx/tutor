# Relay result kinds

A failed request's `result` node carries `kind`: one flat name per case. The
app draws the case from `kind` alone (a glyph, and a calm or error tint) and
speaks its own fixed sentence for it. It never shows or speaks the worker's
`error` string.

```json
{"ok":false,"at":1791731346000,"code":"bad_request","reason":"paste_statement",
 "error":"that problem has no public statement; paste it","retry":false,
 "kind":"refused_paste_statement"}
```

**`result.kind` is not the request's `kind`.** `req.kind` names what was asked
(`session_start`, `lc_open`, ...). `result.kind` names how it failed, and it
appears only in the `result` node. Phases have no `kind`: they live in
`claim.phase` / `meta.busy.phase` under their wire names.

**`kind` is not `error_kind` either.** `error_kind` (`DOCS-contract.md` §4a,
`tutor/codes.py`) is a coarse class: outage, model failure, bad request,
`other`. `kind` names one case per code, reason and next step. The app reads
`kind`.

## Source of truth

- Python: `tutor/relay/kinds.py` (`CASES`). `RequestError.kind`, `result_of`
  (`tutor/relay/errors.py`) and the curriculum `RequestError.result`
  (`tutor/curriculum/errors.py`) all read from it.
- Golden file: `contract/relay_kinds.json` (`cases`, `phases`), written by
  `.venv/bin/python scripts/gen_relay_kinds.py`. `tutor/tests/test_relay_kinds.py`
  fails when the file and the mapping drift.
- App: `app/lib/relay/relay_kinds.dart` (derivation for old results),
  `app/lib/ui/relay_cue.dart` (`kindIcons`, `phaseIcon`). The parity test
  `app/test/ui/relay_kinds_test.dart` reads the golden file. Every kind and
  phase there needs its own glyph. No glyph may repeat, and none may be a
  fallback glyph.

## How a kind is chosen

`code` gives the kind. Two fields split a code further:

- `reason`: only `bad_request` + `paste_statement`.
- `next`: `locked` + `review_module`, and `no_card_left` + `review_module` or
  `reviews_due`.

`claude_unavailable`'s `reason` (`rate_limit`, `overloaded`, `network`) does
**not** split it. The app shows one outage cue and switches to the drill in
every case. An unknown code is `worker_error` on the worker side (`err_worker`).

`error`, `reason`, `next`, `due_at`, `module` and the other flat fields stay
on the wire. `error` serves the worker log and old app builds. The rest feed
the due ring and the module tap target.

## Kinds

Calm = the amber call-to-action tint (`CueKind.blocked`), for a next step
rather than a failure. Error = the red tint with a shake (`CueKind.error`).
The app picks the tint by prefix (`blocked_*` and `refused_*` are calm), so a
newer kind gets the right tint even before it has a glyph.

| kind | code (+ split) | glyph (`Icons.`) | tint |
|---|---|---|---|
| `err_bad_request` | `bad_request` | `report_outlined` | error |
| `refused_paste_statement` | `bad_request` + reason `paste_statement` | `content_paste` | calm |
| `err_not_live` | `not_live` | `stop_circle_outlined` | error |
| `err_session_live` | `session_live` | `play_disabled` | error |
| `blocked_locked` | `locked` | `lock_outline` | calm |
| `blocked_locked_review` | `locked` + next `review_module` | `replay` | calm |
| `blocked_cap` | `daily_new_cap` | `add_circle_outline` | calm |
| `blocked_no_card_none` | `no_card_left` (next `none` or absent) | `inventory_2_outlined` | calm |
| `blocked_no_card_review` | `no_card_left` + next `review_module` | `rate_review_outlined` | calm |
| `blocked_no_card_due` | `no_card_left` + next `reviews_due` | `schedule` | calm |
| `err_unknown_card` | `unknown_card` | `search_off` | error |
| `err_plan_conflict` | `plan_conflict` | `merge_type` | error |
| `err_edit_refused` | `edit_refused` | `edit_off` | error |
| `err_focus_refused` | `focus_refused` | `do_not_disturb_alt` | error |
| `err_model` | `model_error` | `running_with_errors` | error |
| `outage_claude` | `claude_unavailable` (any reason) | `power_off` | error |
| `err_unknown_prompt` | `unknown_prompt` | `help_outline` | error |
| `err_gave_up` | `gave_up` | `sync_disabled` | error |
| `err_worker` | `worker_error` | `bug_report_outlined` | error |

Next to the glyph, with no digits and no words (textgate):

- `blocked_no_card_due`: a ring (`DueRing`) whose arc is the time left until
  `due_at`, on a 24 h scale. It is full at 24 h or more, empty when due, and
  redrawn each minute. The exact time stays in the spoken label.
- `blocked_no_card_review`, `blocked_locked_review`: the module's Home mark
  (`ModuleMarkIcon(ModuleMark.done)`, a done module waiting for its review).
  Tapping the mark or the glyph opens that module's review. The module title
  stays in the spoken label and on the Review button.

## Phases

One glyph beside the spinner per `claims.PHASES` name:

| phase | glyph (`Icons.`) |
|---|---|
| `claimed` | `inbox_outlined` |
| `thinking` | `psychology_outlined` |
| `images` | `image_search` |
| `checking_images` | `fact_check_outlined` |
| `publishing` | `publish` |

## Fallbacks and version skew

- Unknown `kind`: generic error glyph `error_outline`, tinted by prefix.
- Unknown phase: `Phase.parse` returns `Phase.unknown` (it never throws),
  drawn as the generic working glyph `more_horiz`.
- Neither case throws or paints text.
- Old app + new server: the old app ignores the extra `kind`.
- New app + old server, or a done-map replay of a result recorded before
  `kind` existed: the app derives the same kind from `code`, `reason` and
  `next` (`kindOfResult`). The parity test checks every golden row with
  `kind` removed.
- Deploy order: web build, then `scripts/tutor_deploy.sh` (server first).
