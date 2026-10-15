/// The client half of the relay protocol (DOCS-contract §4).
///
/// The client PUTs only `requests/{rid}/req` (so a retry never clobbers the
/// worker's `claim`/`result`), then streams `requests/{rid}` until a result
/// lands. A retry re-PUTs the very same `req`: same rid, same `sent_at` (the
/// first Send press), never a new rid.
library;

import 'dart:async';

import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_stream.dart';
import 'package:tutor/util/ulid.dart';

/// A request with its identity fixed, ready to (re)send.
class PendingRequest {
  /// Creates the pair.
  const new(this.rid, this.req);

  /// Request id (ULID).
  final String rid;

  /// The `req` node, written unchanged on every attempt.
  final RequestReq req;
}

/// Where a request stands, as the UI shows it.
sealed class RelayStatus {
  const new();
}

/// The `req` PUT failed; nothing may have arrived. Offer Retry.
class RelayNotSent extends RelayStatus {
  /// Creates the status.
  const new(this.error);

  /// The transport error.
  final Object error;

  /// Text for kuhy.
  String get text => offlineText;
}

/// Written, not claimed yet (the PC may be offline: it waits).
class RelayQueued extends RelayStatus {
  /// Creates the status.
  const new();
}

/// Claimed; the worker is in [phase].
class RelayWorking extends RelayStatus {
  /// Creates the status.
  const new(this.phase, this.attempt);

  /// Worker phase.
  final Phase phase;

  /// Attempt number.
  final int attempt;
}

/// Finished successfully.
class RelayDone extends RelayStatus {
  /// Creates the status.
  const new(this.data);

  /// Kind-specific result data.
  final Json data;
}

/// Finished with an error the worker reported.
class RelayFailed extends RelayStatus {
  /// Creates the status.
  const new({
    required this.code,
    required this.text,
    this.retry = false,
    this.unavailable,
  });

  /// Error code.
  final String? code;

  /// Text for kuhy.
  final String text;

  /// The worker suggests retrying.
  final bool retry;

  /// When Claude is back, for `claude_unavailable` (the drill fallback).
  final Unavailable? unavailable;
}

/// Maps a `requests/{rid}` snapshot to a status.
RelayStatus statusOf(Object? node) {
  final j = node is Json ? node : const <String, dynamic>{};
  final result = objOr(j, 'result');
  if (result != null) {
    final r = RequestResult.fromJson(result);
    if (r.ok) return RelayDone(r.data);
    return RelayFailed(
      code: r.code,
      text: errorText(r.code, r.error),
      retry: r.retry,
      unavailable: r.code == claudeUnavailable
          ? Unavailable.fromError(result)
          : null,
    );
  }
  final claim = objOr(j, 'claim');
  if (claim != null) {
    final c = RequestClaim.fromJson(claim);
    return RelayWorking(c.phase, c.attempt);
  }
  return const RelayQueued();
}

/// Sends requests and follows them to their result.
class RequestRelay {
  /// Creates the relay for device [dev].
  new({
    required this.client,
    required this.stream,
    required this.dev,
    required this.ulid,
    int Function()? now,
  }) : _now = now ?? (() => DateTime.now().millisecondsSinceEpoch);

  /// REST client.
  final RtdbClient client;

  /// SSE transport.
  final RtdbStream stream;

  /// This install's device id.
  final String dev;

  /// rid source.
  final UlidGenerator ulid;
  final int Function() _now;

  /// Fixes rid and `sent_at` for [body]: call once per Send press.
  PendingRequest prepare(RequestBody body) => PendingRequest(
    ulid.next(),
    RequestReq(kind: body.kind, dev: dev, sentAt: _now(), body: body.body),
  );

  /// The same request under a NEW rid, same `sent_at`: how a result with
  /// `retry:true` is re-sent (the old rid is done on the worker).
  PendingRequest renew(PendingRequest pending) =>
      PendingRequest(ulid.next(), pending.req);

  /// Sends [body] and follows it.
  Stream<RelayStatus> send(RequestBody body) => resend(prepare(body));

  /// (Re)PUTs [pending]'s `req` and follows it to its result. Never mints a
  /// new rid: retries are idempotent on the worker's done-map.
  Stream<RelayStatus> resend(PendingRequest pending) async* {
    try {
      await client.put(Paths.requestReq(pending.rid), pending.req.toJson());
    } on Object catch (error) {
      // `on Object`: token failures and network errors alike mean "not
      // sent"; the UI offers Retry with this same pending request.
      yield RelayNotSent(error);
      return;
    }
    yield* watch(pending.rid);
  }

  /// Streams `requests/{rid}` until a result; emits each distinct status.
  Stream<RelayStatus> watch(String rid) async* {
    Object? tree;
    String? last;
    await for (final event in stream.listen(Paths.request(rid))) {
      tree = applyEvent(tree, event);
      RelayStatus status;
      try {
        status = statusOf(tree);
      } on FormatException catch (error) {
        // RTDB content is untrusted: a malformed claim/result ends the
        // follow loudly instead of spinning on "queued" forever.
        status = RelayFailed(code: null, text: 'Unreadable reply: $error');
      }
      final key = _describe(status);
      if (key != last) {
        last = key;
        yield status;
      }
      if (status is RelayDone || status is RelayFailed) return;
    }
  }

  static String _describe(RelayStatus s) => switch (s) {
    RelayWorking(:final phase, :final attempt) => 'working $phase $attempt',
    _ => s.runtimeType.toString(),
  };
}
