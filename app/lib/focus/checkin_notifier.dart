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
  /// already armed. Its action button ("Still working") is a check-in.
  Future<void> schedule(Duration after);

  /// The timer stopped or lapsed: drop the armed prompt, any notification on
  /// screen and (Android) the foreground service.
  Future<void> cancel();

  /// Taps on the action while the app is alive: the tap time, unix ms.
  Stream<int> get confirmations;

  /// Taps made while the app was not running, oldest first (tap times, unix
  /// ms), each returned once. The timer drains this on start and on resume
  /// and sends each as a `focus_event` `checkin` with that `ts`.
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
