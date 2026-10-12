/// An [RtdbStream] whose events the test pushes by path.
library;

import 'dart:async';

import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

/// The fake transport.
class FakeStream implements RtdbStream {
  /// Open listens by path (the latest one per path).
  final Map<String, StreamController<RtdbEvent>> listens = {};

  /// The query of the latest listen per path.
  final Map<String, Map<String, String>> queries = {};

  @override
  RtdbClient get client => throw UnimplementedError();

  @override
  Stream<RtdbEvent> listen(
    String path, {
    Map<String, String> query = const {},
  }) {
    queries[path] = query;
    return (listens[path] = StreamController<RtdbEvent>()).stream;
  }
}
