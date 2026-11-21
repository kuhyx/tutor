import 'dart:convert';
import 'dart:io';

import 'package:crdt_sync/crdt_sync.dart' show Argon2Params, E2eLockReason;
import 'package:crdt_sync_flutter/crdt_sync_flutter.dart'
    show kE2ePassphraseKey;
import 'package:crdt_sync_flutter/testing/fake_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/e2e_gate.dart';
import 'package:tutor/sync/e2e_seal.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';

import '../support/fake_rtdb.dart';

// The seal itself: e2e_seal_test.dart.
const _fast = Argon2Params(memoryKiB: 8, iterations: 1, parallelism: 1);

final Map<String, dynamic> _vectors = jsonDecode(
  File('../contract/e2e_vectors.json').readAsStringSync(),
) as Map<String, dynamic>;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('E2eGate', () {
    RtdbClient needy(FakeRtdb db) => RtdbClient(
      databaseUrl: 'https://fake',
      idToken: () async => 'tok',
      httpClient: db.client().httpClient,
      namespace: '',
      sealRequired: true,
    );

    test('unlocks from the keystore and makes the header once', () async {
      installFakeSecureStorage(initial: {kE2ePassphraseKey: 'test-passphrase'});
      final db = FakeRtdb();
      final client = needy(db);
      final gate = E2eGate(client: client, params: _fast);
      expect(await gate.unlock(), isTrue);
      expect(gate.locked, isFalse);
      expect(await gate.unlock(), isTrue); // already open
      final header = getAt(db.root, kE2eLayout.e2ePath);
      expect(header, isA<String>());
      await client.put(Paths.live, {'session': 'x'});
      expect(jsonEncode(getAt(db.root, Paths.live)), contains(kSealedKey));
      // A second device with the same passphrase reads the same key.
      final other = needy(db);
      expect(await E2eGate(client: other, params: _fast).unlock(), isTrue);
      expect(await other.get(Paths.live), {'session': 'x'});
    });

    test('stays locked without, or with a wrong, passphrase', () async {
      installFakeSecureStorage();
      final db = FakeRtdb();
      final gate = E2eGate(client: needy(db), params: _fast);
      expect(await gate.unlock(), isFalse);
      expect(gate.reason, E2eLockReason.needsPassphrase.name);
      db.root = setAt(db.root, kE2eLayout.e2ePath, {'not': 'a header'});
      installFakeSecureStorage(initial: {kE2ePassphraseKey: 'x'});
      final bad = E2eGate(client: needy(db), params: _fast);
      expect(await bad.unlock(), isFalse);
      expect(bad.reason, E2eLockReason.badHeader.name);
    });

    test('opens a header and a unit the Python worker made', () async {
      final h = _vectors['header'] as Map<String, dynamic>;
      installFakeSecureStorage(
        initial: {kE2ePassphraseKey: h['passphrase'] as String},
      );
      final db = FakeRtdb()..root = setAt(null, h['path'] as String, h['text']);
      final unit = h['unit'] as Map<String, dynamic>;
      db.root = setAt(db.root, '${Paths.root}/${unit['path']}', unit['stored']);
      final client = needy(db);
      expect(await E2eGate(client: client, params: _fast).unlock(), isTrue);
      expect(await client.get('${Paths.root}/${unit['path']}'), unit['value']);
      installFakeSecureStorage(initial: {kE2ePassphraseKey: 'wrong'});
      final wrong = E2eGate(client: needy(db), params: _fast);
      expect(await wrong.unlock(), isFalse);
      expect(wrong.reason, E2eLockReason.wrongKey.name);
    });
  });

  test('the header store reads strings only and never deletes', () async {
    final db = FakeRtdb()..root = setAt(null, 'tutor/e2e', {'x': 1});
    final store = E2eHeaderStore(db.client());
    expect(await store.getFileText('tutor/e2e'), '{x: 1}');
    expect(await store.getFileText('tutor/none'), isNull);
    expect(await store.listDirectory('tutor'), isEmpty);
    expect(await store.canAccessRemote(), isTrue);
    expect(() => store.deleteFile('tutor/e2e'), throwsA(anything));
    store.close();
    expect(const E2eLayoutError('x').toString(), 'E2eLayoutError: x');
  });
}
