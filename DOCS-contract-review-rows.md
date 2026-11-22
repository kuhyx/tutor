# Tutor contract: review minute rows (C1, review part; 2026-11-22)

leetcode-guard pays one LeetCode credit per 12 signed tutor minutes of a
module. It counts only credit rows whose signed `detail` has `subject` and
`module`: a lesson row has them (`DOCS-contract.md` §7, C1), and so does a
review minute row, written by the app Review (`tutor/review_credit.py`, entry
ids `review-<YYYYMMDD>-<device>-m<n>`) or the PC drill (`tutor/drill.py`,
`drill-<stamp>-<id>-m<n>`). AnkiDroid rows (`anki-...`) never get them.

## The row
A review minute row stays `kind: "credit"` with its `entry_id`, `day`,
`created_at` and every `detail` field as before (`session_id`, `block`,
`minutes`, `active_seconds`, `ended_at`, `checks_passed`, `checks_total`).
Its signed `detail` also holds three keys:

- `subject`: the subject slug.
- `module`: the module id of the card whose review completed the row's last
  minute, the same review that sets `ended_at` (the card's `module` in the
  subject's `cards.json`; for the drill, the answered card's module). One row
  has one module, even if it covers several minutes.
- `activity`: `"review"`. A lesson row never has an `activity` key.

When that card or its subject is gone, the row is written without the three
keys, logged at warning, and still pays its tutor minutes. A reader ignores it.

## Rows written before the keys existed
Rows are never rewritten or removed. For a review minute of today (local day)
whose row lacks the keys, the credit pass appends a twin: the same `entry_id`,
`minutes`, `ended_at`, `day`, `created_at` and other fields, plus the three
keys, signed again (`tutor/ledger_twin.py`). The untagged original stays.
Only a verified row is re-signed; a verified tagged row of that `entry_id`
means nothing is written, so it happens once. It runs in every normal credit
pass, so the first pass after a deploy fixes today's rows. Older days stay
untagged.

## What a reader must do
- Pay tutor minutes as before: earned_time and `ledger_pay.paying` pay a
  repeated `entry_id` once at its smallest count; the twin repeats the count,
  so the tutor rung pays the same (`tutor/tests/test_review_tag.py`).
- Count per module from one row per `entry_id`, the tagged one if there are
  two; never count both.
