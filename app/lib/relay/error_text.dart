/// User-facing text for request error codes (DOCS-contract §4).
///
/// The worker's `error` string is shown to kuhy as the detail; this adds a
/// plain headline per code so an unknown or empty `error` still reads well.
/// Tracebacks never reach the client.
library;

const _headlines = {
  'bad_request': 'The PC could not read that request.',
  'not_live': 'That session is no longer live.',
  'locked': 'That is locked until earlier modules are mastered.',
  'daily_new_cap': 'Ten new cards today already. Reviews still work.',
  'no_card_left': 'No card left to teach in this subject right now.',
  'unknown_card': 'That card does not exist (any more).',
  'plan_conflict': 'The plan changed meanwhile. Reload it and try again.',
  'edit_refused': 'The card edit was refused.',
  'model_error': 'The tutor model failed on this turn.',
  'gave_up': 'The PC gave up after three attempts.',
  'worker_error': 'Something broke on the PC.',
};

/// Network failure while sending (the request may not have arrived).
const offlineText = 'Not sent: no connection. Retry sends the same request.';

/// Shown while the PC is offline (DOCS-contract §5).
const pcOfflineText = 'PC offline: replies wait; reviews still work';

/// The headline for [code] (generic for unknown codes).
String headlineFor(String? code) =>
    _headlines[code] ?? 'The request failed${code == null ? '' : ' ($code)'}.';

/// Headline plus the worker's [error] detail when it adds something.
String errorText(String? code, String? error) {
  final headline = headlineFor(code);
  final detail = error?.trim() ?? '';
  return detail.isEmpty ? headline : '$headline $detail';
}
