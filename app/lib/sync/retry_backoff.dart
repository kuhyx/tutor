/// Sync that retries by itself (`~/.claude/rules/offline-first.instructions.md`,
/// rule b): a failed push arms one timer that runs it again, waiting twice
/// as long after each failure, up to [kMaxRetry]; a push that got through
/// resets the wait.
library;

import 'dart:async';

/// The longest wait between two retries.
const kMaxRetry = Duration(minutes: 5);

/// One backoff timer around [run].
class RetryBackoff {
  /// Creates the backoff; the first retry waits [first].
  new(this.run, {this.first = const Duration(seconds: 5)}) : _delay = first;

  /// The push to run again.
  final Future<Object?> Function() run;

  /// Wait after the first failure.
  final Duration first;

  Duration _delay;
  Timer? _timer;

  /// How long the next armed retry waits.
  Duration get wait => _delay;

  /// Whether a retry is waiting to run.
  bool get armed => _timer?.isActive ?? false;

  /// A push failed: arms the retry unless one is already waiting.
  void failed() {
    if (armed) return;
    _timer = Timer(_delay, () => unawaited(run()));
    final next = _delay * 2;
    _delay = next > kMaxRetry ? kMaxRetry : next;
  }

  /// A push got through: drops a waiting retry and resets the wait.
  void ok() {
    dispose();
    _delay = first;
  }

  /// Drops a waiting retry.
  void dispose() => _timer?.cancel();
}
