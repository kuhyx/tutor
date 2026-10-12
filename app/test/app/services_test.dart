import 'package:crdt_sync/crdt_sync.dart' show InMemoryCredentialStore;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/storage/kv_store.dart';

void main() {
  test('open wires every service around one device id', () async {
    final kv = MemoryKv();
    final s = await TutorServices.open(
      const FirebaseConfig(
        apiKey: 'k',
        databaseUrl: 'https://db',
        syncUid: 'u',
        serverClientId: '',
      ),
      store: InMemoryCredentialStore(),
      kv: kv,
      httpClient: MockClient((_) async => http.Response('null', 200)),
    );
    expect(isDeviceId(s.dev), isTrue);
    expect(s.relay.dev, s.dev);
    expect(s.events.dev, s.dev);
    expect(s.kv, same(kv));
    expect(await s.auth.hasSession(), isFalse);
    expect(s.presence.state.value.name, 'checking');
    expect(s.home.events, same(s.events));
    expect(s.config.syncUid, 'u');
    expect(s.client, same(s.relay.client));
    expect(s.stream, same(s.relay.stream));
  });

  test('default stores: shared_preferences and the keystore', () async {
    SharedPreferences.setMockInitialValues({});
    final s = await TutorServices.open(
      const FirebaseConfig(
        apiKey: 'k',
        databaseUrl: 'https://db',
        syncUid: 'u',
        serverClientId: '',
      ),
      httpClient: MockClient((_) async => http.Response('null', 200)),
    );
    expect(s.kv, isA<PrefsKv>());
    // No platform channel in tests: the keystore read fails, which reads
    // as "signed out" rather than crashing.
    expect(await s.auth.hasSession(), isFalse);
  });
}
