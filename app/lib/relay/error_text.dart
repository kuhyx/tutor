/// The app's own sentences for request failures (DOCS-contract §4,
/// DOCS-relay-kinds.md): spoken labels only (textgate), one per kind. The
/// worker's `error` string is never shown or spoken.
library;

import 'package:tutor/model/request.dart';
import 'package:tutor/relay/relay_kinds.dart';

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
  'focus_refused': 'The focus project was refused.',
  'worker_error': 'Something broke on the PC.',
};

/// Sentences for kinds that split a code (the rest speak their code's).
const Map<String, String> _kindSentences = {
  refusedPasteStatement: 'This problem has no public statement; paste it.',
};

/// A claim or result the app could not parse.
const unreadableText = 'The reply from the PC could not be read.';

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

/// The spoken sentence of [kind] (else of [code]): fixed, from the app.
String kindText(String? kind, String? code) =>
    _kindSentences[kind] ?? headlineFor(code);

/// What the worker is doing, as the busy line shows it (§4 phases).
String phaseText(Phase phase) => switch (phase) {
  Phase.claimed => 'The PC picked it up...',
  Phase.thinking => 'Tutor is thinking...',
  Phase.images => 'Finding pictures...',
  Phase.checkingImages => 'Checking the pictures...',
  Phase.publishing => 'Publishing the reply...',
  Phase.unknown => 'The PC is working on it...',
};
