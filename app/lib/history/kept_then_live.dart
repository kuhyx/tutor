/// Offline-first reads (`~/.claude/rules/offline-first.instructions.md`):
/// the copy kept on this install first, then the live answer.
library;

import 'dart:developer';

import 'package:tutor/sync/rtdb_client.dart';

/// One answer of a [keptThenLive] stream.
class Fetched<T> {
  /// Creates the answer.
  const new(this.value, {required this.live, this.offline = false});

  /// The data.
  final T value;

  /// From the database (else from the copy on this install).
  final bool live;

  /// The database could not be reached: [value] is the kept copy.
  final bool offline;
}

/// The kept copy first (when there is one), then the live answer; when the
/// live fetch fails after a kept copy, that copy again marked offline.
/// With nothing kept a failure is the stream's error.
Stream<Fetched<T>> keptThenLive<T>(
  Future<T?> Function() kept,
  Future<T> Function() live,
) async* {
  final copy = await kept();
  if (copy != null) yield Fetched(copy, live: false);
  try {
    yield Fetched(await live(), live: true);
  } on RtdbError catch (error) {
    if (copy == null) rethrow;
    log('database unreachable; History from disk', level: 900, error: error);
    yield Fetched(copy, live: false, offline: true);
  }
}
