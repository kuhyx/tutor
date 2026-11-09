import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:tutor/focus/checkin_card.dart';
import 'package:tutor/focus/checkin_notifier.dart';
import 'package:tutor/focus/event_queue.dart';
import 'package:tutor/review/review_items.dart';
import 'package:tutor/storage/kv_store.dart';

part 'focus_timer_background.dart';

const _key = 'focus.timer';
const _tick = Duration(seconds: 1);

/// A gap above this between taps stops the counting (focus_project rule).
const lapseAfter = Duration(minutes: 10);

/// Longer than this out of the foreground ends the run, at the moment the
/// app left the screen.
const backgroundGrace = Duration(seconds: 60);

/// A check-in card rated sooner than this after it appeared is graded but
/// proves no presence: it sends no beat.
const presenceFloor = Duration(seconds: 1);

/// The focus timer: taps become queued `focus_event`s with the tap time.
/// The check-in is one recall card ([checkinCard], picked at the
/// prompt); with none, the old "Still working" tap ([wantsTap]).
class FocusTimer extends ChangeNotifier {
  /// Creates the timer; send delivers one queued event.
  new({
    required this._kv,
    required this._queue,
    required this._send,
    this._notifier = const NoopCheckinNotifier(),
    this._pick,
    this._platform = 'phone',
    this._background = backgroundGrace,
    int Function()? now,
  }) : _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  final KvStore _kv;
  final FocusEventQueue _queue;
  final FocusSender _send;
  final FocusCheckinNotifier _notifier;
  final CheckinPicker? _pick;
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
  // The check-in card: in memory only, so a restart drops it ungraded.
  ReviewItem? _card;
  int _cardShownMs = 0;
  int? _pickedFor; // the beat (_lastMs) the last pick was made for
  bool _picking = false;
  final _opened = StreamController<void>.broadcast();
  int _screens = 0;

  int get _gapMs => _now() - _lastMs;

  bool _tooLate(int gapMs) => gapMs > lapseAfter.inMilliseconds;

  /// Counting right now.
  bool get isRunning => _started && !_tooLate(_gapMs);

  /// A check-in was missed: counting stopped at the last tap.
  bool get isLapsed => _started && _tooLate(_gapMs);

  /// Time counted in this run: finished gaps plus the open one.
  Duration get counted =>
      Duration(milliseconds: _countedMs + (isRunning ? _gapMs : 0));

  /// True from [checkinEvery] after the last tap: ask for a check-in.
  bool get checkinDue => isRunning && _gapMs >= checkinEvery.inMilliseconds;

  /// The card this check-in asks (it stays after a lapse), or null.
  ReviewItem? get checkinCard => _card;

  /// The check-in is due and no card could be picked: the old tap.
  bool get wantsTap =>
      checkinDue && _card == null && !_picking && _pickedFor == _lastMs;

  /// A notification was clicked: the app should show the Focus screen.
  Stream<void> get openRequests => _opened.stream;

  /// A Focus screen is open (it [attach]es while mounted).
  bool get onScreen => _screens > 0;

  /// A Focus screen opened.
  void attach() => _screens++;

  /// A Focus screen closed.
  void detach() => _screens--;

  /// This device's clock (ms), shared with the check-in card's review.
  int nowMs() => _now();

  /// Restores the saved run, takes taps made off-screen, starts ticking.
  /// Every caller gets the same future, so a second one never sees the timer
  /// before the saved run is back.
  Future<void> load() => _loading ??= _load();

  Future<void> _load() async {
    await _restore();
    // A notification only opens the app; the check-in is the graded card.
    _taps = _notifier.confirmations.listen((_) => _opened.add(null));
    await _notifier.takePending(); // taps an older build stored: not counted
    _arm();
    unawaited(flush());
    await pickIfDue();
    notifyListeners();
  }

  /// Picks the check-in card once per beat, when the check-in is due or the
  /// run lapsed (the reopened app offers it with "Missed a check-in").
  Future<void> pickIfDue() async {
    final pick = _pick;
    if (_card != null || _picking || _pickedFor == _lastMs) return;
    if (!checkinDue && !isLapsed) return;
    final beat = _lastMs;
    _pickedFor = beat;
    if (pick == null) return;
    _picking = true;
    final ReviewItem? item;
    try {
      item = await pick();
    } finally {
      _picking = false;
    }
    if (_disposed || _lastMs != beat || !_started) return;
    _card = item;
    _cardShownMs = _now();
    notifyListeners();
  }

  /// The check-in card was rated at [at] (the review's own time). Within
  /// 600 s of the last beat it is a `card` beat (unless rated under
  /// [presenceFloor]); after the lapse it starts a new segment.
  Future<void> cardRated(int at) async {
    final item = _card;
    if (item == null) return;
    _dropCard();
    if (!_started || _tooLate(at - _lastMs)) {
      _countedMs = 0;
      await _tap('start', at);
    } else if (at - _cardShownMs < presenceFloor.inMilliseconds) {
      notifyListeners(); // graded, but no beat: the next tick picks again
      return;
    } else {
      _countedMs += at - _lastMs;
      await _tap('card', at, item: item);
    }
    await _notifier.schedule(checkinEvery);
  }

  void _dropCard() {
    _card = null;
    _pickedFor = null;
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
    unawaited(pickIfDue());
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _ticker?.cancel();
    _grace?.cancel();
    _lifecycle?.dispose();
    unawaited(_taps?.cancel());
    unawaited(_opened.close());
    super.dispose();
  }
}
