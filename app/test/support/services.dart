/// Services over a fake DB and fake stream, for widget tests.
library;

import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart' show InMemoryCredentialStore;
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/rev_watcher.dart';
import 'package:tutor/sync/rtdb_stream.dart';
import 'package:tutor/util/ulid.dart';

import 'fake_rtdb.dart';

/// Device id of the test install.
const testDev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';

/// Config every test build uses.
const testConfig = FirebaseConfig(
  apiKey: 'k',
  databaseUrl: 'https://fake',
  syncUid: 'right',
  serverClientId: 'client',
);

/// Services over a fake DB and a fake [stream]; the IdP answers [uid].
TutorServices services(
  FakeRtdb db,
  RtdbStream stream, {
  String uid = 'right',
  KvStore? kv,
}) {
  final store = kv ?? MemoryKv();
  final client = db.client();
  final auth = TutorAuth(
    config: testConfig,
    store: InMemoryCredentialStore(),
    httpClient: MockClient(
      (_) async => http.Response(
        jsonEncode({
          'localId': uid,
          'idToken': 'id',
          'refreshToken': 'r',
          'expiresIn': '3600',
        }),
        200,
      ),
    ),
  );
  final ulid = UlidGenerator();
  final events = EventLog(client: client, kv: store, dev: testDev, ulid: ulid);
  final relay = RequestRelay(
    client: client,
    stream: stream,
    dev: testDev,
    ulid: ulid,
  );
  return TutorServices(
    config: testConfig,
    dev: testDev,
    kv: store,
    auth: auth,
    client: client,
    stream: stream,
    relay: relay,
    presence: PresenceWatcher(stream),
    rev: RevWatcher(stream, yieldTo: relay.inFlight),
    events: events,
    home: HomeLoader(client: client, kv: store, events: events),
    catalog: Catalog(client: client, kv: store),
    history: HistoryRepo(client),
    feedback: FeedbackSender(client: client, dev: testDev, ulid: ulid),
  );
}
