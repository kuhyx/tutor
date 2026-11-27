// A cold start with no network opens the app: the e2e header is kept on
// this install, and a token refresh that cannot reach Google reads as an
// unreachable database (every offline fallback catches RtdbError).
import 'package:crdt_sync/crdt_sync.dart' show Argon2Params, FirebaseAuthError;
import 'package:crdt_sync_flutter/crdt_sync_flutter.dart'
    show kE2ePassphraseKey;
import 'package:crdt_sync_flutter/testing/fake_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/e2e_gate.dart';
import 'package:tutor/sync/rtdb_client.dart';

import '../support/fake_rtdb.dart';

const _fast = Argon2Params(memoryKiB: 8, iterations: 1, parallelism: 1);

RtdbClient _client(
  FakeRtdb db,
  KvStore? kv, {
  Future<String> Function()? token,
}) => RtdbClient(
  databaseUrl: 'https://fake',
  idToken: token ?? () async => 'tok',
  httpClient: db.client().httpClient,
  namespace: '',
  sealRequired: true,
  kv: kv,
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('a cold start offline unlocks from the kept header', () async {
    installFakeSecureStorage(initial: {kE2ePassphraseKey: 'test-passphrase'});
    final db = FakeRtdb();
    final kv = MemoryKv();
    expect(
      await E2eGate(client: _client(db, kv), params: _fast).unlock(),
      true,
    );
    expect(kv.data[RtdbClient.kHeaderKey], isA<String>());
    db.offline = true;
    final cold = _client(db, kv);
    expect(await E2eGate(client: cold, params: _fast).unlock(), isTrue);
    // Other reads still fail loudly offline: only the header is kept here.
    await expectLater(cold.get(Paths.live), throwsA(isA<RtdbError>()));
  });

  test('offline with no kept header stays an error', () async {
    installFakeSecureStorage(initial: {kE2ePassphraseKey: 'test-passphrase'});
    final db = FakeRtdb()..offline = true;
    final gate = E2eGate(client: _client(db, MemoryKv()), params: _fast);
    await expectLater(gate.unlock(), throwsA(isA<RtdbError>()));
    final bare = E2eGate(client: _client(db, null), params: _fast);
    await expectLater(bare.unlock(), throwsA(isA<RtdbError>()));
  });

  test('a token refresh with no network is an unreachable database', () async {
    final db = FakeRtdb();
    final offline = _client(
      db,
      null,
      token: () async =>
          throw FirebaseAuthError('network error trying to refresh: x'),
    );
    await expectLater(offline.uri('a'), throwsA(isA<RtdbError>()));
    final signedOut = _client(
      db,
      null,
      token: () async => throw FirebaseAuthError('not signed in'),
    );
    await expectLater(signedOut.uri('a'), throwsA(isA<FirebaseAuthError>()));
  });
}
