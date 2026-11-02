import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:tutor/focus/checkin_notifier.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/storage/kv_store.dart';

part 'focus_timer_background.dart';

const _key = 'focus.timer';
const _tick = Duration(seconds: 1);

/// A gap above this between taps stops the counting (focus_project rule).
const lapseAfter = Duration(minutes: 10);

/// Longer than this out of the foreground ends the run, at the moment the
/// app left the screen.
const backgroundGrace = Duration(seconds: 60);

/// The focus timer: taps become queued `focus_event`s with the tap time.
class FocusTimer extends ChangeNotifier {
  /// Creates the timer; send delivers one queued event.
  new({
    required this._kv,
    required this._queue,
    required this._send,
    this._notifier = const NoopCheckinNotifier(),
    this._platform = 'phone',
    this._background = backgroundGrace,
    int Function()? now,
  }) : _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  final KvStore _kv;
  final FocusEventQueue _queue;
  final FocusSender _send;
  final FocusCheckinNotifier _notifier;
  final String _platform;
  final Duration _background;
  final int Function() _now;
  bool _started = false;
  Future<void>? _loading;
  bool _disposed = false;
  bool _lapseHandled = false;
  Future<void> _flushes = Future.value();
  int _lastMs = 0;
  int _countedMs = 0;
  Timer? _ticker;
  StreamSubscription<int>? _taps;
  AppLifecycleListener? _lifecycle;
  Timer? _grace;
  Future<void> _leaving = Future.value();
  QueuedFocusEvent? _pendingStop;

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
  /// Every caller gets the same future, so a second one never sees the timer
  /// before the saved run is back.
  Future<void> load() => _loading ??= _load();

  Future<void> _load() async {
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

  /// The run is live: loads the saved one first, then starts a stopped or
  /// lapsed timer; a live run is left alone (a deep link may ask twice).
  Future<void> ensureRunning() async {
    await load();
    if (!isRunning) await start();
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

  Future<void> _tap(String event, int ts, {bool started = true}) async {
    await _dropPendingStop();
    await _queue.enqueue(event, ts: ts, platform: _platform);
    _started = started;
    _lastMs = ts;
    _lapseHandled = false;
    await _save();
    _arm();
    notifyListeners();
    unawaited(flush());
  }

  void _changed() {
    if (!_disposed) notifyListeners();
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
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _ticker?.cancel();
    _grace?.cancel();
    _lifecycle?.dispose();
    unawaited(_taps?.cancel());
    super.dispose();
  }
}
