/// One request at a time for one screen action, with Retry that re-sends the
/// SAME request (same rid, same `sent_at`: DOCS-contract §4), never a new
/// one.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';

/// Runs requests through a [RequestRelay] and exposes their status.
class RequestRunner {
  /// Creates the runner.
  new(this.relay);

  /// The relay.
  final RequestRelay relay;

  /// Latest status; null before the first request.
  final ValueNotifier<RelayStatus?> status = ValueNotifier(null);

  PendingRequest? _pending;
  StreamSubscription<RelayStatus>? _sub;
  Completer<RelayStatus>? _done;

  /// Whether a request is in flight (queued or being worked on).
  bool get busy => switch (status.value) {
    RelayQueued() || RelayWorking() => true,
    _ => false,
  };

  /// Whether the last request can be re-sent unchanged.
  bool get canRetry => switch (status.value) {
    RelayNotSent() => true,
    RelayFailed(:final retry) => retry,
    _ => false,
  };

  /// Sends [body]; completes with the final status.
  Future<RelayStatus> run(RequestBody body) {
    final pending = relay.prepare(body);
    _pending = pending;
    return _follow(relay.resend(pending));
  }

  /// Re-sends the last request unchanged.
  Future<RelayStatus> retry() {
    final pending = _pending;
    if (pending == null) {
      throw StateError('nothing to retry');
    }
    return _follow(relay.resend(pending));
  }

  /// Forgets the last status (the banner was dismissed).
  void clear() => status.value = null;

  Future<RelayStatus> _follow(Stream<RelayStatus> statuses) {
    _settle();
    unawaited(_sub?.cancel());
    final done = _done = Completer<RelayStatus>();
    status.value = const RelayQueued();
    _sub = statuses.listen((s) => status.value = s, onDone: _settle);
    return done.future;
  }

  // Completes the current caller with the latest status (also when a newer
  // request replaces it, so no await is left hanging).
  void _settle() {
    final done = _done;
    _done = null;
    if (done != null) done.complete(status.value!);
  }

  /// Stops following (the result still lands in RTDB for later).
  Future<void> dispose() async {
    await _sub?.cancel();
    _settle();
    status.dispose();
  }
}
