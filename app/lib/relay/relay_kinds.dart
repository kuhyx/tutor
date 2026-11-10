/// A failed result's `kind` (DOCS-relay-kinds.md): one flat name per case,
/// which the app draws as a glyph and a calm or error tint. The server sends
/// it in the result node; an older server (or a done-map replay of an older
/// result) does not, so the same kind is derived here from `code`, `reason`
/// and `next`, as `tutor/relay/kinds.py` does. Unknown code: null (the
/// generic error glyph).
library;

import 'package:tutor/model/json.dart';

/// The kind the coach answers with the paste box.
const refusedPasteStatement = 'refused_paste_statement';

/// The claude-outage kind (the drill fallback).
const outageClaude = 'outage_claude';

const Map<String, String> _plain = {
  'bad_request': 'err_bad_request',
  'not_live': 'err_not_live',
  'session_live': 'err_session_live',
  'locked': 'blocked_locked',
  'daily_new_cap': 'blocked_cap',
  'no_card_left': 'blocked_no_card_none',
  'unknown_card': 'err_unknown_card',
  'plan_conflict': 'err_plan_conflict',
  'edit_refused': 'err_edit_refused',
  'focus_refused': 'err_focus_refused',
  'model_error': 'err_model',
  'claude_unavailable': outageClaude,
  'unknown_prompt': 'err_unknown_prompt',
  'gave_up': 'err_gave_up',
  'worker_error': 'err_worker',
};

const Map<(String, String), String> _byReason = {
  ('bad_request', 'paste_statement'): refusedPasteStatement,
};

const Map<(String, String), String> _byNext = {
  ('locked', 'review_module'): 'blocked_locked_review',
  ('no_card_left', 'review_module'): 'blocked_no_card_review',
  ('no_card_left', 'reviews_due'): 'blocked_no_card_due',
};

/// The kind of a failed [result] node: its own `kind`, else derived.
String? kindOfResult(Json result) {
  final sent = result['kind'];
  if (sent is String && sent.isNotEmpty) return sent;
  final code = result['code'];
  if (code is! String) return null;
  final reason = result['reason'];
  final next = result['next'];
  return (reason is String ? _byReason[(code, reason)] : null) ??
      (next is String ? _byNext[(code, next)] : null) ??
      _plain[code];
}
