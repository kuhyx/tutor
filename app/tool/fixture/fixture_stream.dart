/// An [RtdbStream] over the fixture database: every listen gets a connect
/// and the node's snapshot; `presence/workers` then a fresh beat, so the
/// header shows "PC online" as with a live worker.
library;

import 'dart:async';

import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

/// Snapshot-only stream.
class FixtureStream implements RtdbStream {
  /// Creates the stream over [root] (read at listen time).
  new(this.client, this.root);

  @override
  final RtdbClient client;

  /// Current tree.
  final Object? Function() root;

  @override
  Stream<RtdbEvent> listen(
    String path, {
    Map<String, String> query = const {},
  }) async* {
    yield const RtdbConnected();
    yield RtdbPut('/', getAt(root(), path));
    if (path == Paths.workers) {
      await Future<void>.delayed(const Duration(milliseconds: 300));
      yield RtdbPut('/', getAt(root(), path));
    }
    // Stay open like a real listen.
    await Completer<void>().future;
  }
}
