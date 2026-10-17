/// One request at a time for one screen action, with Retry that re-sends the
/// SAME request (same rid, same `sent_at`: DOCS-contract §4), never a new
/// one.
///
/// A request with no result and no progress for [RequestRunner.stallAfter]
/// is "stalled": still in flight, but the screen may offer Send again. That
/// sends the SAME rid when the body is unchanged, so a reply that was only
/// late lands once (the worker's done-map re-answers a done rid and never
/// re-runs it, DOCS-contract §4).
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/request_relay.dart';

/// How long the session waits in silence before offering Send again.
const sessionStallAfter = Duration(minutes: 3);

/// Runs requests through a [RequestRelay] and exposes their status.
class RequestRunner {
  /// Creates the runner; with [stallAfter] set, [stalled] turns on once a
  /// request shows no result and no new phase for that long (null: never,
  /// and no timer runs).
  new(this.relay, {this.stallAfter}) {
    status.addListener(_restartStall);
  }

  /// How long an in-flight request may be silent before it counts as
  /// stalled; null disables the check.
  final Duration? stallAfter;

  /// The relay.
  final RequestRelay relay;

  /// Latest status; null before the first request.
  final ValueNotifier<RelayStatus?> status = ValueNotifier(null);

  /// True once the in-flight request has shown neither a result nor a new
  /// phase for [stallAfter]. Cleared by any progress, a result, or a resend.
  final ValueNotifier<bool> stalled = ValueNotifier(false);

  Timer? _stallTimer;
  PendingRequest? _pending;
  RequestBody? _lastBody;

  /// The body of the last request [run] sent (null before the first).
  RequestBody? get lastBody => _lastBody;
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
  ///
  /// While [stalled] and [body] is exactly the in-flight request's, this
  /// re-PUTs that request under its own rid instead of minting a new one: a
  /// late result then answers both presses once. A different body is a new
  /// message and gets a new rid.
  Future<RelayStatus> run(RequestBody body) {
    final last = _pending;
    if (stalled.value && busy && last != null && _same(last, body)) {
      return _follow(relay.resend(last), keepCaller: true);
    }
    final pending = relay.prepare(body);
    _pending = pending;
    _lastBody = body;
    return _follow(relay.resend(pending));
  }

  /// Re-sends the last request: unchanged when it never arrived; under a
  /// new rid (same `sent_at`) when the worker answered `retry:true`, since
  /// that rid is done on the worker (DOCS-contract §4).
  Future<RelayStatus> retry() {
    var pending = _pending;
    if (pending == null) {
      throw StateError('nothing to retry');
    }
    if (status.value is RelayFailed) {
      pending = _pending = relay.renew(pending);
    }
    return _follow(relay.resend(pending));
  }

  /// Forgets the last status (the banner was dismissed).
  void clear() => status.value = null;

  static bool _same(PendingRequest p, RequestBody body) =>
      p.req.kind == body.kind &&
      jsonEncode(p.req.body) == jsonEncode(body.body);

  // Restarts the silence timer on every status change (a phase change is
  // progress); a final status or none stops it.
  void _restartStall() {
    _stallTimer?.cancel();
    _stallTimer = null;
    stalled.value = false;
    final after = stallAfter;
    if (after != null && busy) {
      _stallTimer = Timer(after, () => stalled.value = true);
    }
  }

  // [keepCaller]: the same request again, so the awaiting caller stays the
  // one that its result settles (not settled early by this resend).
  Future<RelayStatus> _follow(
    Stream<RelayStatus> statuses, {
    bool keepCaller = false,
  }) {
    final kept = keepCaller ? _done : null;
    if (kept == null) _settle();
    unawaited(_sub?.cancel());
    final done = _done = kept ?? Completer<RelayStatus>();
    status.value = const RelayQueued();
    _restartStall(); // also when the status was already queued
    _sub = statuses.listen((s) {
      status.value = s;
      // A final status settles the caller at once; the stream's own end
      // can lag behind its last event (it first cancels its RTDB listen).
      if (s is RelayDone || s is RelayFailed || s is RelayNotSent) _settle();
    }, onDone: _settle);
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
    _stallTimer?.cancel();
    await _sub?.cancel();
    _settle();
    status.removeListener(_restartStall);
    stalled.dispose();
    status.dispose();
  }
}
