part of 'focus_timer.dart';

/// Leaving the app ends the run (kuhy: "when I exit the app make the clock
/// stop counting"): hidden over [backgroundGrace] or detached, the stop is
/// stamped with the hide time, queued at once (a killed process still
/// delivers it) and held until the grace ends.
extension FocusBackground on FocusTimer {
  /// Watches the app lifecycle (the phone build calls this once).
  void watchLifecycle() {
    _lifecycle ??= AppLifecycleListener(
      onHide: () => unawaited(leftForeground()),
      onShow: () => unawaited(returnedToForeground()),
      onDetach: () => unawaited(leftForeground(commit: true)),
    );
  }

  /// The app left the screen at [ts] (default now); [commit] skips the grace.
  Future<void> leftForeground({int? ts, bool commit = false}) {
    final at = ts ?? _now();
    return _leaving = _leaving.then((_) async {
      if (isRunning && _pendingStop == null) {
        _pendingStop = await _queue.enqueue(
          'stop',
          ts: at,
          platform: _platform,
          hold: true,
        );
        await _save();
        _grace?.cancel();
        _grace = Timer(_background, () => unawaited(_commitStop()));
      }
      if (commit) await _commitStop();
    });
  }

  /// The app is visible again: within the grace the run simply goes on.
  Future<void> returnedToForeground() =>
      _leaving = _leaving.then((_) => _dropPendingStop());

  Future<void> _dropPendingStop() async {
    final p = _pendingStop;
    if (p == null) return;
    _grace?.cancel();
    _pendingStop = null;
    await _queue.remove(p.rid);
    await _save();
  }

  Future<void> _commitStop() async {
    final p = _pendingStop;
    if (p == null) return;
    _grace?.cancel();
    _pendingStop = null;
    _endRunAt(p.ts);
    _queue.release(p.rid);
    await _save();
    _arm();
    await _notifier.cancel();
    _changed();
    unawaited(flush());
  }

  void _endRunAt(int ts) {
    if (_started && !_tooLate(ts - _lastMs)) _countedMs += ts - _lastMs;
    _started = false;
    _lastMs = ts;
    _dropCard();
  }
}
