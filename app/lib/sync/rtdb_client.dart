/// Firebase RTDB over REST for the tutor's tree: the shared `rtdb_relay`
/// client bound to the tutor's layout (DOCS-contract §2, §12).
///
/// Offline-first at the door: the e2e header is kept in `kv` so a cold
/// start with no network still opens the key (the e2e gate reads it through
/// [RtdbClient.get]), and a token refresh that cannot reach Google throws
/// `RtdbError` like any other unreachable read, so every screen's kept-copy
/// fallback catches it.
library;

import 'dart:developer';

import 'package:crdt_sync/crdt_sync.dart' show FirebaseAuthError;
import 'package:rtdb_relay/rtdb_relay.dart' as relay;
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/e2e_seal.dart';

export 'package:rtdb_relay/rtdb_relay.dart'
    show ConditionalResult, IdTokenSource, RtdbError, Tagged, keyRangeQuery;

/// The REST client over the tutor's layout.
class RtdbClient extends relay.RtdbClient {
  /// Creates a client for [databaseUrl] authenticated by `idToken`; with
  /// [kv] the e2e header is kept there.
  new({
    required super.databaseUrl,
    required super.idToken,
    super.httpClient,
    super.namespace,
    super.sealer,
    super.sealRequired,
    this.kv,
  }) : super(layout: kTutorLayout);

  /// Where the e2e header is kept (null: not kept).
  final KvStore? kv;

  /// Key of the kept e2e header.
  static const kHeaderKey = 'sync.e2e_header';

  @override
  Future<Uri> uri(String path, {Map<String, String> query = const {}}) async {
    try {
      return await super.uri(path, query: query);
    } on FirebaseAuthError catch (error) {
      // Signed out stays an auth error; only "no network" is unreachable.
      if (!error.message.startsWith('network error')) rethrow;
      throw relay.RtdbError('network error: $path: ${error.message}');
    }
  }

  @override
  Future<Object?> get(
    String path, {
    Map<String, String> query = const {},
  }) async {
    final store = kv;
    if (store == null || path != kE2eLayout.e2ePath) {
      return await super.get(path, query: query);
    }
    try {
      final header = await super.get(path, query: query);
      if (header is String) await store.set(kHeaderKey, header);
      return header;
    } on relay.RtdbError catch (error) {
      final kept = await store.get(kHeaderKey);
      if (kept == null) rethrow;
      log('e2e header unreachable; kept copy', level: 900, error: error);
      return kept;
    }
  }
}
