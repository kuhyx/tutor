import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crdt_sync/crdt_sync.dart'
    show Argon2Params, E2eCipher, E2eLockReason;
import 'package:crdt_sync_flutter/crdt_sync_flutter.dart'
    show kE2ePassphraseKey;
import 'package:crdt_sync_flutter/testing/fake_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/sync/e2e_gate.dart';
import 'package:tutor/sync/e2e_seal.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/sync/rtdb_stream.dart';

import '../support/fake_rtdb.dart';

const _fast = Argon2Params(memoryKiB: 8, iterations: 1, parallelism: 1);
const _rid = '01J0000000000000000000000R';

final Map<String, dynamic> _vectors = jsonDecode(
  File('../contract/e2e_vectors.json').readAsStringSync(),
) as Map<String, dynamic>;

TutorSealer _sealer() =>
    TutorSealer(E2eCipher(_hex(_vectors['key_hex'] as String)));

List<int> _hex(String s) => [
  for (var i = 0; i < s.length; i += 2)
    int.parse(s.substring(i, i + 2), radix: 16),
];

RtdbClient _sealed(FakeRtdb db) => db.client()..sealer = _sealer();

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'a pushed request is ciphertext at rest, read back in the clear',
    () async {
      final db = FakeRtdb();
      final client = _sealed(db);
      final stored = await client.put(Paths.requestReq(_rid), {
        'kind': 'message',
        'dev': 'd1',
        'created': {'.sv': 'timestamp'},
        'body': {'session': '20261012-170448-5b71', 'text': 'secret words'},
      });
      final atRest = jsonEncode(db.root);
      expect(atRest, isNot(contains('secret words')));
      expect(atRest, isNot(contains('"text"')));
      expect(atRest, isNot(contains('"kind"')));
      // The server timestamp the credit maths needs stays clear and resolved.
      expect(
        getAt(db.root, '${Paths.requestReq(_rid)}/created'),
        db.serverTime,
      );
      expect((stored! as Map)['body'], {
        'session': '20261012-170448-5b71',
        'text': 'secret words',
      });
      final read = await client.get(Paths.request(_rid)) as Map?;
      expect((read!['req'] as Map)['created'], db.serverTime);
      expect(((read['req'] as Map)['body'] as Map)['text'], 'secret words');
    },
  );

  test('the vectors pin the rules and open what Python sealed', () async {
    expect(_vectors['root'], kE2eLayout.prefix);
    expect(_vectors['sealed_key'], kSealedKey);
    for (final r in (_vectors['rules'] as List).cast<Map<String, dynamic>>()) {
      expect(
        classifyE2e(e2eParts(r['path'] as String)).kind.name,
        r['kind'],
        reason: r['path'] as String,
      );
    }
    final s = _sealer();
    for (final u in (_vectors['units'] as List).cast<Map<String, dynamic>>()) {
      final path = u['path'] as String;
      expect(await s.open(path, u['stored']), u['value'], reason: path);
      // And Dart's own seal round-trips through the same layout.
      expect(await s.open(path, await s.seal(path, u['value'])), u['value']);
    }
  });

  test('every path the app writes has a rule', () async {
    final s = _sealer();
    String rel(String p) => p.substring(Paths.root.length + 1);
    final writes = <String, Object?>{
      Paths.requestReq(_rid): {'kind': 'x', 'created': 1},
      Paths.feedback(_rid): {'text': 'x'},
      Paths.uploadChunk(_rid, 1): 'aGVsbG8=',
      Paths.logEvent('0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10', _rid): {'r': 3},
      '${Paths.prefs}/current_subject': 'car',
      Paths.client('0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10'): {
        'platform': 'web',
        'seen': 1,
      },
      '${Paths.session('20261012-170448-5b71')}/user': {'archived': true},
    };
    for (final e in writes.entries) {
      final sealed = await s.seal(rel(e.key), e.value);
      expect(jsonEncode(sealed), contains(kSealedKey), reason: e.key);
      expect(await s.open(rel(e.key), sealed), e.value, reason: e.key);
    }
    await expectLater(
      s.seal('secrets', {'a': 1}),
      throwsA(isA<E2eLayoutError>()),
    );
    await expectLater(
      s.sealPatch('sessions/s/msgs/m0001', {'text': 'x'}),
      throwsA(isA<E2eLayoutError>()),
    );
    await expectLater(
      s.open('stats/today/x', 1),
      throwsA(isA<E2eLayoutError>()),
    );
    expect(
      await s.open('prefs', {
        'current_subject': {kSealedKey: 'AQ=='},
        'other': 'legacy',
      }),
      {'other': 'legacy'},
    );
    expect(await s.open('sessions', [1]), [1]);
    expect(await s.seal('presence/clients/d', {'x': null}), isNull);
  });

  test('patch, tagged reads, below-unit reads and events open', () async {
    final db = FakeRtdb();
    final client = _sealed(db);
    final session = Paths.session('20261012-170448-5b71');
    await client.patch('$session/user', {'archived': true});
    await client.put('${Paths.stats}/today', {'new_cap': 25});
    expect(jsonEncode(db.root), isNot(contains('new_cap')));
    expect(await client.get('${Paths.stats}/today/new_cap'), 25);
    expect(await client.get('${Paths.stats}/today/nope/x'), isNull);
    expect((await client.getTagged('$session/user')).value, {'archived': true});
    final put = await openEvent(
      client,
      session,
      RtdbPut('/', getAt(db.root, session)),
    );
    expect((put as RtdbPut).data, {
      'user': {'archived': true},
    });
    final patch = await openEvent(
      client,
      Paths.stats,
      RtdbPatch('/', {'today': getAt(db.root, '${Paths.stats}/today')}),
    );
    expect((patch as RtdbPatch).data, {
      'today': {'new_cap': 25},
    });
    expect(
      await openEvent(client, session, const RtdbKeepAlive()),
      isA<RtdbKeepAlive>(),
    );
    final cond = await client.putIfMatch('${Paths.stats}/today', {'n': 1}, 'x');
    expect(cond.value, {'n': 1});
    // Outside the e2e root nothing is sealed (the header lives there).
    await client.put('tutor/e2e', 'header');
    expect(getAt(db.root, 'tutor/e2e'), 'header');
  });

  test('a client that needs a key sends nothing without one', () async {
    final db = FakeRtdb();
    final client = RtdbClient(
      databaseUrl: 'https://fake',
      idToken: () async => 'tok',
      httpClient: db.client().httpClient,
      namespace: '',
      sealRequired: true,
    );
    await expectLater(
      client.put(Paths.requestReq(_rid), {'kind': 'x'}),
      throwsA(isA<RtdbError>()),
    );
    await expectLater(client.get(Paths.live), throwsA(isA<RtdbError>()));
    await expectLater(client.delete(Paths.live), throwsA(isA<RtdbError>()));
    expect(db.log, isEmpty);
    expect(E2eGate(client: client).locked, isTrue);
    expect(E2eGate(client: db.client()).locked, isFalse);
    expect(await E2eGate(client: db.client()).unlock(), isTrue);
  });

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

  test(
    'a stream event inside a unit drops the connection, then resyncs',
    () async {
      final sse = StreamController<List<int>>();
      final client = RtdbClient(
        databaseUrl: 'https://db',
        idToken: () async => 'tok',
        httpClient: MockClient.streaming(
          (req, _) async => http.StreamedResponse(sse.stream, 200),
        ),
        namespace: '',
      )..sealer = _sealer();
      final events = <RtdbEvent>[];
      final sub = RtdbStream(
        client,
        sleep: (_) => Completer<void>().future,
      ).listen('${Paths.stats}/today').listen(events.add);
      sse.add(utf8.encode('event: put\ndata: {"path":"/x","data":1}\n\n'));
      await pumpEventQueue();
      expect(events.last, isA<RtdbDisconnected>());
      await sub.cancel();
    },
  );
}
