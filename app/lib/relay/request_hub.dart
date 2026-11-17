/// Every request in flight, followed over ONE listen (DOCS-contract §4, §9):
/// the shared `rtdb_relay` hub on the tutor's `requests` node.
library;

import 'package:rtdb_relay/rtdb_relay.dart' as relay;
import 'package:tutor/model/ids.dart';

/// The shared `requests` listen.
class RequestHub extends relay.RequestHub {
  /// Creates the hub over `stream`.
  new(relay.RtdbStream stream) : super(stream, Paths.requests);
}
