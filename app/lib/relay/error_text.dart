/// User-facing text for request error codes (DOCS-contract §4).
///
/// The worker's `error` string is shown to kuhy as the detail; this adds a
/// plain headline per code so an unknown or empty `error` still reads well.
/// Tracebacks never reach the client.
library;

import 'package:tutor/model/request.dart';
import 'package:tutor/relay/blocked.dart';

/// The error code that sends the app to the model-free drill.
const claudeUnavailable = 'claude_unavailable';

const Map<String, String> _headlines = {
  'bad_request': 'The PC could not read that request.',
  'not_live': 'That session is no longer live.',
  'session_live': 'Another session is live.',
  'locked': 'That is locked until earlier modules are reviewed.',
  'daily_new_cap': "You reached today's limit of new cards.",
  'no_card_left': 'No card left to teach in this subject right now.',
  'unknown_card': 'That card does not exist (any more).',
  'plan_conflict': 'The plan changed meanwhile. Reload it and try again.',
  'edit_refused': 'The card edit was refused.',
  'model_error': 'The tutor model failed on this turn.',
  claudeUnavailable: 'Claude is not available right now.',
  'gave_up': 'The PC gave up after three attempts.',
  'worker_error': 'Something broke on the PC.',
};

/// Network failure while sending (the request may not have arrived).
const offlineText = 'Not sent: no connection. Retry sends the same request.';

/// A sent request with no result and no progress for minutes: Send is open
/// again (the same text resends the same request, so nothing doubles).
const noReplyText = 'No reply from PC \u2014 send again';

/// Shown while the PC is offline (DOCS-contract §5).
const pcOfflineText = 'PC offline: replies wait; reviews still work';

/// The headline for [code] (generic for unknown codes).
String headlineFor(String? code) =>
    _headlines[code] ?? 'The request failed${code == null ? '' : ' ($code)'}.';

/// Headline plus the worker's [error] detail when it adds something.
String errorText(String? code, String? error) {
  final headline = headlineFor(code);
  // A blocking code's detail names the subject id and repeats the headline:
  // never shown (the app's own line comes from blocked.dart).
  final detail = blockedCodes.contains(code) ? '' : error?.trim() ?? '';
  return detail.isEmpty ? headline : '$headline $detail';
}

/// What the worker is doing, as the busy line shows it (§4 phases).
String phaseText(Phase phase) => switch (phase) {
  Phase.claimed => 'The PC picked it up...',
  Phase.thinking => 'Tutor is thinking...',
  Phase.images => 'Finding pictures...',
  Phase.checkingImages => 'Checking the pictures...',
  Phase.publishing => 'Publishing the reply...',
};
