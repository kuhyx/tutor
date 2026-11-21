part of 'focus_timer.dart';

/// The run's state machine: the saved run, a tap becoming a queued event,
/// and the one-second tick.
extension _FocusRun on FocusTimer {
  Future<void> _restore() async {
    final raw = await _kv.get(_key);
    if (raw == null) return;
    final j = jsonDecode(raw) as Map<String, dynamic>;
    _started = j['running'] as bool;
    _lastMs = j['last'] as int;
    _countedMs = j['counted'] as int;
    final stored = j['pendingStop'];
    if (stored == null) return;
    // A process killed in the grace left its stop queued: finish it now.
    _endRunAt(QueuedFocusEvent.fromJson(stored as Map<String, dynamic>).ts);
    await _save();
    await _notifier.cancel();
  }

  Future<void> _save() => _kv.set(
    _key,
    jsonEncode({
      'running': _started,
      'last': _lastMs,
      'counted': _countedMs,
      if (_pendingStop != null) 'pendingStop': _pendingStop!.toJson(),
    }),
  );

  Future<void> _tap(
    String event,
    int ts, {
    bool started = true,
    ReviewItem? item,
  }) async {
    await _dropPendingStop();
    await _queue.enqueue(
      event,
      ts: ts,
      platform: _platform,
      subject: item?.subject,
      card: item?.cardId,
    );
    _started = started;
    _lastMs = ts;
    _dropCard();
    _lapseHandled = false;
    await _save();
    _arm();
    _notify();
    unawaited(flush());
  }

  void _arm() {
    _ticker?.cancel();
    _ticker = _started ? Timer.periodic(_tick, (_) => _onTick()) : null;
  }

  /// Once per run -> lapsed transition the notifier is cancelled, so no
  /// prompt or service outlives the counting (Android also does it natively).
  void _onTick() {
    if (isLapsed && !_lapseHandled) {
      _lapseHandled = true;
      unawaited(_notifier.cancel());
    }
    unawaited(pickIfDue());
    _notify();
  }
}
