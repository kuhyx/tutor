/// An [RtdbStream] over the fixture database: every listen gets a connect
/// and the node's snapshot; `presence/workers` then a fresh beat, so the
/// header shows "PC online" as with a live worker; `rev` then, once, the
/// scheduled [FixtureStream.change] (the worker finishing a module).
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
  new(this.client, this.root, {this.change});

  @override
  final RtdbClient client;

  /// Current tree.
  final Object? Function() root;

  /// Applied `after` the first `rev` listen opens, then streamed.
  final ({Duration after, void Function() apply})? change;
  bool _changed = false;

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
    final change = this.change;
    if (path == Paths.rev && change != null && !_changed) {
      _changed = true;
      await Future<void>.delayed(change.after);
      change.apply();
      yield RtdbPut('/', getAt(root(), path));
    }
    // Stay open like a real listen.
    await Completer<void>().future;
  }
}
