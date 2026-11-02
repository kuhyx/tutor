import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:tutor/focus/checkin_notifier.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/storage/kv_store.dart';

const _key = 'focus.timer';
const _tick = Duration(seconds: 1);

/// A gap above this between taps stops the counting (focus_project rule).
const lapseAfter = Duration(minutes: 10);

/// The focus timer: taps become queued `focus_event`s with the tap time.
class FocusTimer extends ChangeNotifier {
  /// Creates the timer; send delivers one queued event.
  new({
    required this._kv,
    required this._queue,
    required this._send,
    this._notifier = const NoopCheckinNotifier(),
    this._platform = 'phone',
    int Function()? now,
  }) : _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  final KvStore _kv;
  final FocusEventQueue _queue;
  final FocusSender _send;
  final FocusCheckinNotifier _notifier;
  final String _platform;
  final int Function() _now;
  bool _started = false;
  bool _loaded = false;
  bool _disposed = false;
  Future<void> _flushes = Future.value();
  int _lastMs = 0;
  int _countedMs = 0;
  Timer? _ticker;
  StreamSubscription<int>? _taps;

  int get _gapMs => _now() - _lastMs;

  bool _tooLate(int gapMs) => gapMs > lapseAfter.inMilliseconds;

  /// Counting right now.
  bool get isRunning => _started && !_tooLate(_gapMs);

  /// A check-in was missed: counting stopped at the last tap.
  bool get isLapsed => _started && _tooLate(_gapMs);

  /// Time counted in this run: finished gaps plus the open one.
  Duration get counted =>
      Duration(milliseconds: _countedMs + (isRunning ? _gapMs : 0));

  /// True from [checkinEvery] after the last tap: ask "Still working?".
  bool get checkinDue => isRunning && _gapMs >= checkinEvery.inMilliseconds;

  /// Restores the saved run, takes taps made off-screen, starts ticking.
  Future<void> load() async {
    if (_loaded) return;
    _loaded = true;
    await _restore();
    _taps = _notifier.confirmations.listen((ts) => unawaited(checkin(ts)));
    for (final ts in await _notifier.takePending()) {
      await checkin(ts);
    }
    _arm();
    unawaited(flush());
    notifyListeners();
  }

  /// Starts a run (also the way back after a lapse).
  Future<void> start() async {
    _countedMs = 0;
    await _tap('start', _now());
    await _notifier.schedule(checkinEvery);
  }

  /// "Still working": counts the gap since the last tap when it was short.
  Future<void> checkin([int? ts]) async {
    final at = ts ?? _now();
    if (!_started || _tooLate(at - _lastMs)) {
      _countedMs = 0;
      await _tap('start', at);
    } else {
      _countedMs += at - _lastMs;
      await _tap('checkin', at);
    }
    await _notifier.schedule(checkinEvery);
  }

  /// Ends the run.
  Future<void> stop() async {
    if (!_started) return;
    if (isRunning) _countedMs += _gapMs;
    await _tap('stop', _now(), started: false);
    await _notifier.cancel();
  }

  /// Sends the queued taps; an absent PC leaves them queued.
  Future<void> flush() {
    final run = _flushes.then((_) => _queue.flush(_send));
    _flushes = run.then<void>((_) {}, onError: (_) {});
    return run.then((_) {
      if (!_disposed) notifyListeners();
    });
  }

  Future<void> _restore() async {
    final raw = await _kv.get(_key);
    if (raw == null) return;
    final j = jsonDecode(raw) as Map<String, dynamic>;
    _started = j['running'] as bool;
    _lastMs = j['last'] as int;
    _countedMs = j['counted'] as int;
  }

  Future<void> _save() => _kv.set(
    _key,
    jsonEncode({'running': _started, 'last': _lastMs, 'counted': _countedMs}),
  );

  Future<void> _tap(String event, int ts, {bool started = true}) async {
    await _queue.enqueue(event, ts: ts, platform: _platform);
    _started = started;
    _lastMs = ts;
    await _save();
    _arm();
    notifyListeners();
    unawaited(flush());
  }

  void _arm() {
    _ticker?.cancel();
    _ticker = _started ? Timer.periodic(_tick, (_) => notifyListeners()) : null;
  }

  @override
  void dispose() {
    _disposed = true;
    _ticker?.cancel();
    unawaited(_taps?.cancel());
    super.dispose();
  }
}
