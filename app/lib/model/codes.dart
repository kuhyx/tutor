/// The machine codes the worker sends beside its sentences (DOCS-contract
/// §4a): the Dart mirror of `tutor/codes.py`, both tested against
/// `contract/codes.json`. The app paints a glyph per code
/// (`ui/code_glyphs.dart`); the sentence stays the spoken label. Every
/// parser maps a missing or unknown value to `other` (the generic glyph).
library;

T _parse<T extends Enum>(
  List<T> values,
  Object? wire,
  String Function(T) w,
  T other,
) {
  for (final v in values) {
    if (w(v) == wire) return v;
  }
  return other;
}

/// A failed request's `code`.
enum RelayCode {
  /// Unreadable or refused request.
  badRequest('bad_request'),

  /// The session is no longer live.
  notLive('not_live'),

  /// Another session is live.
  sessionLive('session_live'),

  /// Locked until a module is reviewed.
  locked,

  /// Today's new cards are used up.
  dailyNewCap('daily_new_cap'),

  /// No card left to teach.
  noCardLeft('no_card_left'),

  /// The card does not exist.
  unknownCard('unknown_card'),

  /// The plan changed meanwhile.
  planConflict('plan_conflict'),

  /// A card edit was refused.
  editRefused('edit_refused'),

  /// A focus project request was refused.
  focusRefused('focus_refused'),

  /// The tutor model failed.
  modelError('model_error'),

  /// Claude is out (`reason`).
  claudeUnavailable('claude_unavailable'),

  /// The drill prompt is gone.
  unknownPrompt('unknown_prompt'),

  /// The PC gave up after its attempts.
  gaveUp('gave_up'),

  /// Something broke on the PC.
  workerError('worker_error'),

  /// Not in the contract (or missing).
  other;

  new([this._wire]);
  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses [wire]; unknown = [other].
  static RelayCode parse(Object? wire) =>
      _parse(values, wire, (c) => c.wire, other);
}

/// A failed result's `reason`.
enum FailReason {
  /// The coach could not fetch the problem: paste its statement.
  pasteStatement('paste_statement'),

  /// Claude's rate limit.
  rateLimit('rate_limit'),

  /// Claude is overloaded.
  overloaded,

  /// Claude is unreachable.
  network,

  /// Not in the contract (or missing).
  other;

  new([this._wire]);
  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses [wire]; unknown = [other].
  static FailReason parse(Object? wire) =>
      _parse(values, wire, (c) => c.wire, other);
}

/// What a card-edit notice did (`notice_kinds`, same index as `notices`).
enum NoticeKind {
  /// Card removed.
  removed,

  /// Card added.
  added,

  /// Mnemonic set.
  mnemonicSet('mnemonic_set'),

  /// Mnemonic cleared.
  mnemonicCleared('mnemonic_cleared'),

  /// Card split.
  split,

  /// Card rewritten.
  updated,

  /// Not in the contract, or an older message with no kinds.
  other;

  new([this._wire]);
  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses [wire]; unknown = [other].
  static NoticeKind parse(Object? wire) =>
      _parse(values, wire, (c) => c.wire, other);
}

/// Why a generation or request failed (`error_kind`).
enum ErrorKind {
  /// Claude's rate limit.
  claudeLimit('claude_limit'),

  /// Claude is overloaded.
  claudeOverloaded('claude_overloaded'),

  /// Claude is unreachable.
  claudeNetwork('claude_network'),

  /// The model failed (bad answer, crash, timeout).
  modelFailed('model_failed'),

  /// Too few usable sources were found.
  sourcesMissing('sources_missing'),

  /// Too few cards passed the checks.
  tooFewCards('too_few_cards'),

  /// The request was refused as malformed.
  badRequest('bad_request'),

  /// Not in the contract (or missing).
  other;

  new([this._wire]);
  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses [wire]; unknown = [other].
  static ErrorKind parse(Object? wire) =>
      _parse(values, wire, (c) => c.wire, other);
}

/// Why Claude is out (`unavailable.reason`, `claude_unavailable`'s `reason`).
enum UnavailableReason {
  /// The rate limit.
  rateLimit('rate_limit'),

  /// Overloaded.
  overloaded,

  /// Unreachable.
  network,

  /// The PC did not say (or said something unknown).
  other;

  new([this._wire]);
  final String? _wire;

  /// Name on the wire.
  String get wire => _wire ?? name;

  /// Parses [wire]; unknown = [other].
  static UnavailableReason parse(Object? wire) =>
      _parse(values, wire, (c) => c.wire, other);
}

/// Why the session clock paused (`clock.paused_reason`): the worker sends
/// one of two fixed sentences, pinned in the contract.
enum PauseReason {
  /// A low-effort reply earned nothing.
  lowEffort('low-effort reply'),

  /// No reply within the reply timeout.
  stalled('no reply for 10 min'),

  /// Not in the contract.
  other('');

  new(this.wire);

  /// The sentence on the wire.
  final String wire;

  /// Parses [wire]; unknown = [other].
  static PauseReason parse(Object? wire) =>
      _parse(values.sublist(0, 2), wire, (c) => c.wire, other);
}
