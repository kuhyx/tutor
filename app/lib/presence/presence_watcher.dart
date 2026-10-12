/// "Is the PC online?" from `presence/workers` (DOCS-contract §5).
///
/// The worker PUTs a heartbeat every 30 s. The client never compares `beat`
/// with its own wall clock (phones drift): it watches for *changes* and
/// declares the PC offline after 75 s without one, timed by a Dart [Timer],
/// which runs on the monotonic clock. Every (re)connect resends the whole
/// node, and that snapshot proves nothing about now, so a connect shows
/// "checking" until the next real beat.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

/// What the header shows.
enum PcPresence {
  /// Connected, waiting for a heartbeat newer than the snapshot.
  checking,

  /// A heartbeat arrived within the timeout.
  online,

  /// No heartbeat for the timeout, or no worker registered at all.
  offline,
}

/// Streams `presence/workers` while started (foreground only, §9).
class PresenceWatcher {
  /// Creates the watcher.
  new(this._stream, {this.timeout = const Duration(seconds: 75)});

  final RtdbStream _stream;

  /// Silence after which the PC counts as offline.
  final Duration timeout;

  /// Current state; listen to it from the UI.
  final ValueNotifier<PcPresence> state = ValueNotifier(PcPresence.checking);

  // Cancelled in stop(); the lint cannot see across methods.
  // ignore: cancel_subscriptions
  StreamSubscription<RtdbEvent>? _sub;
  Timer? _timer;
  Object? _tree;
  bool _awaitSnapshot = true;

  /// Starts listening (idempotent).
  void start() {
    if (_sub != null) return;
    state.value = PcPresence.checking;
    _sub = _stream.listen(Paths.workers).listen(_on);
  }

  /// Stops listening (app backgrounded); the state is kept as last known.
  Future<void> stop() async {
    _timer?.cancel();
    _timer = null;
    final sub = _sub;
    _sub = null;
    await sub?.cancel();
  }

  /// Releases the notifier.
  Future<void> dispose() async {
    await stop();
    state.dispose();
  }

  void _on(RtdbEvent event) {
    switch (event) {
      case RtdbConnected():
        _tree = null;
        _awaitSnapshot = true;
        state.value = PcPresence.checking;
        _arm();
      case RtdbPut() || RtdbPatch():
        _tree = applyEvent(_tree, event);
        if (_tree == null) {
          // No worker registered (clean exit DELETEs its node): offline now
          // rather than after a 75 s wait for a beat that cannot come.
          state.value = PcPresence.offline;
          _timer?.cancel();
        } else if (_awaitSnapshot) {
          // The snapshot is old news; keep "checking" until a real beat.
          _arm();
        } else {
          state.value = PcPresence.online;
          _arm();
        }
        _awaitSnapshot = false;
      case RtdbDisconnected() ||
          RtdbKeepAlive() ||
          RtdbCancel() ||
          RtdbAuthRevoked():
        // Not beats. A drop keeps the timer running: if nothing arrives in
        // time, "offline" is the honest answer whether the PC or the
        // network is down.
        break;
    }
  }

  void _arm() {
    _timer?.cancel();
    _timer = Timer(timeout, () => state.value = PcPresence.offline);
  }
}
