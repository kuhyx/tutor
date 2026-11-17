/// "Did the catalog change?" from the `rev` node (DOCS-contract §3, §9):
/// the shared `rtdb_relay` watcher on the tutor's `rev`.
library;

import 'package:rtdb_relay/rtdb_relay.dart' as relay;
import 'package:tutor/model/ids.dart';

export 'package:rtdb_relay/rtdb_relay.dart' show foregroundFor;

/// `catalog` of a `rev` tree; 0 when absent, as Home reads it.
int catalogRev(Object? rev) => relay.revOf(rev, 'catalog');

/// Streams `rev` while someone listens and the app is in front.
class RevWatcher extends relay.RevWatcher {
  /// Creates the watcher; `binding` (tests) reports the app lifecycle;
  /// while `yieldTo` is above 0 the listen is closed.
  new(relay.RtdbStream stream, {super.binding, super.yieldTo})
    : super(stream, Paths.rev);

  /// The new `rev.catalog` each time it moves.
  Stream<int> get catalogChanges => changesOf('catalog');

  /// The new `rev.stats` each time it moves (the worker rewrote `stats`).
  Stream<int> get statsChanges => changesOf('stats');
}
