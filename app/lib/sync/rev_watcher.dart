/// "Did the catalog change?" from the `rev` node (DOCS-contract §3, §9).
///
/// One shared listen for every screen: `catalogChanges` is a broadcast
/// stream whose first listener opens the SSE and whose last cancel closes
/// it, so Home under Plan costs one connection, not two. The listen also
/// pauses while the app is hidden and resumes when it is back in front.
///
/// Only real moves are emitted, `rev.catalog` on `catalogChanges` and
/// `rev.stats` on `statsChanges`; the full snapshot every (re)connect
/// resends while a value is unchanged is not a move. A snapshot whose value
/// *did* change (the worker finished a module while the app was hidden) is.
library;

import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

/// `catalog` of a `rev` tree; 0 when absent, as Home reads it.
int catalogRev(Object? rev) => _revOf(rev, 'catalog');

int _revOf(Object? rev, String key) {
  final value = rev is Map<String, dynamic> ? rev[key] : null;
  return value is num ? value.toInt() : 0;
}

/// Whether the app counts as in front for [state] (null: not reported yet).
/// `inactive` keeps whatever was decided before: desktop web reports it on
/// a mere focus change, which is no reason to drop or reopen the listen.
bool? foregroundFor(AppLifecycleState? state) => switch (state) {
  null || AppLifecycleState.resumed => true,
  AppLifecycleState.inactive => null,
  AppLifecycleState.hidden ||
  AppLifecycleState.paused ||
  AppLifecycleState.detached => false,
};

/// Streams `rev` while someone listens and the app is in front.
class RevWatcher {
  /// Creates the watcher; `binding` (tests) reports the app lifecycle.
  new(this._stream, {this._binding});

  final RtdbStream _stream;
  final WidgetsBinding? _binding;

  late final StreamController<int> _out = StreamController.broadcast(
    onListen: _open,
    onCancel: _release,
  );

  late final StreamController<int> _statsOut = StreamController.broadcast(
    onListen: _open,
    onCancel: _release,
  );

  // Cancelled in _disconnect(); the lint cannot see across methods.
  // ignore: cancel_subscriptions
  StreamSubscription<RtdbEvent>? _sub;
  AppLifecycleListener? _lifecycle;
  bool _foreground = true;
  Object? _tree;
  int? _last;
  int? _lastStats;

  /// The new `rev.catalog` each time it moves.
  Stream<int> get catalogChanges => _out.stream;

  /// The new `rev.stats` each time it moves (the worker rewrote `stats`).
  Stream<int> get statsChanges => _statsOut.stream;

  bool get _wanted => _out.hasListener || _statsOut.hasListener;

  /// Whether the SSE listen is open (tests).
  bool get listening => _sub != null;

  /// Tells the watcher the app went to the back (false) or front (true).
  void foreground({required bool visible}) {
    _foreground = visible;
    visible ? _connect() : unawaited(_disconnect());
  }

  /// Closes the listen and the stream.
  Future<void> dispose() async {
    await _out.close();
    await _statsOut.close();
    await _close();
  }

  // The first listener of either stream opens the listen, the last closes it.
  void _open() {
    if (_lifecycle != null) return;
    final binding = _binding ?? WidgetsBinding.instance;
    _foreground = foregroundFor(binding.lifecycleState) ?? true;
    _lifecycle = AppLifecycleListener(
      binding: binding,
      onStateChange: (state) {
        final visible = foregroundFor(state);
        if (visible != null) foreground(visible: visible);
      },
    );
    _connect();
  }

  Future<void> _release() async {
    if (!_wanted) await _close();
  }

  Future<void> _close() async {
    _lifecycle?.dispose();
    _lifecycle = null;
    await _disconnect();
  }

  void _connect() {
    if (_sub != null || !_foreground || !_wanted) return;
    _tree = null;
    _sub = _stream.listen(Paths.rev).listen(_on, onDone: () => _sub = null);
  }

  Future<void> _disconnect() async {
    final sub = _sub;
    _sub = null;
    await sub?.cancel();
  }

  void _on(RtdbEvent event) {
    if (event is RtdbConnected) _tree = null;
    if (event is! RtdbPut && event is! RtdbPatch) return;
    _tree = applyEvent(_tree, event);
    final now = catalogRev(_tree);
    final before = _last;
    _last = now;
    // The first value ever is the baseline the screens loaded against.
    if (before != null && before != now && !_out.isClosed) _out.add(now);
    final stats = _revOf(_tree, 'stats');
    final was = _lastStats;
    _lastStats = stats;
    if (was != null && was != stats && !_statsOut.isClosed) {
      _statsOut.add(stats);
    }
  }
}
