/// Firebase RTDB over REST for the tutor's tree: the shared `rtdb_relay`
/// client bound to the tutor's layout (DOCS-contract §2, §12).
library;

import 'package:rtdb_relay/rtdb_relay.dart' as relay;
import 'package:tutor/sync/e2e_seal.dart';

export 'package:rtdb_relay/rtdb_relay.dart'
    show ConditionalResult, IdTokenSource, RtdbError, Tagged, keyRangeQuery;

/// The REST client over the tutor's layout.
class RtdbClient extends relay.RtdbClient {
  /// Creates a client for [databaseUrl] authenticated by `idToken`.
  new({
    required super.databaseUrl,
    required super.idToken,
    super.httpClient,
    super.namespace,
    super.sealer,
    super.sealRequired,
  }) : super(layout: kTutorLayout);
}
