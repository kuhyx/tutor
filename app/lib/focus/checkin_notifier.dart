/// The "Still working?" prompt outside the app (Android notification).
///
/// The focus timer (`focus_timer.dart`) asks for a check-in every
/// [checkinEvery]. In the foreground the screen shows its own prompt; this
/// hook adds the system notification. The Android implementation (C2) lives
/// next to the platform code and is passed to `FocusTimer`; the default is
/// [NoopCheckinNotifier].
library;

/// A check-in is due this often while the timer runs (contract: a gap above
/// 10 minutes stops the counting, so ask three minutes earlier: time to see
/// the prompt and tap).
const checkinEvery = Duration(minutes: 7);

/// Platform side of the check-in prompt.
abstract class FocusCheckinNotifier {
  /// Shows a "Still working?" notification after [after], replacing any one
  /// already armed. A click only opens the app (the check-in is the card).
  Future<void> schedule(Duration after);

  /// The timer stopped or lapsed: drop the armed prompt, any notification on
  /// screen and (Android) the foreground service.
  Future<void> cancel();

  /// Clicks on the notification while the app is alive (time, unix ms): the
  /// timer turns each into an `openRequests` event, never a check-in.
  Stream<int> get confirmations;

  /// Taps an older build's "Still working" action stored natively, each
  /// returned once. The timer drains and drops them: they are not counted.
  Future<List<int>> takePending();
}

/// No notification (desktop, tests, and phones without the permission).
class NoopCheckinNotifier implements FocusCheckinNotifier {
  /// Creates the no-op.
  const new();

  @override
  Future<void> schedule(Duration after) async {}

  @override
  Future<void> cancel() async {}

  @override
  Stream<int> get confirmations => const Stream<int>.empty();

  @override
  Future<List<int>> takePending() async => const <int>[];
}
