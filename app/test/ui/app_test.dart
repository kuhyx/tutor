import 'dart:convert';

import 'package:crdt_sync/crdt_sync.dart' show InMemoryCredentialStore;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/ids.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/app.dart';
import 'package:tutor/ui/sign_in_screen.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _config = FirebaseConfig(
  apiKey: 'k',
  databaseUrl: 'https://fake',
  syncUid: 'right',
  serverClientId: 'client',
);

/// Services over a fake DB and fake stream; the IdP answers [uid].
TutorServices services(FakeRtdb db, FakeStream stream, {String uid = 'right'}) {
  final kv = MemoryKv();
  final client = db.client();
  final auth = TutorAuth(
    config: _config,
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
  final events = EventLog(client: client, kv: kv, dev: _dev, ulid: ulid);
  return TutorServices(
    config: _config,
    dev: _dev,
    kv: kv,
    auth: auth,
    client: client,
    stream: stream,
    relay: RequestRelay(client: client, stream: stream, dev: _dev, ulid: ulid),
    presence: PresenceWatcher(stream),
    events: events,
    home: HomeLoader(client: client, kv: kv, events: events),
  );
}

void main() {
  late FakeRtdb db;
  late FakeStream stream;

  setUp(() {
    db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1/subjects/car/meta', {
        'title': 'How a car works',
        'status': 'draft',
        'created': 1,
        'rev': 1,
        'origin': 'generated',
      });
    db.root = setAt(db.root, 'tutor/v1/stats/today', {
      'day': '2026-10-12',
      'credited_minutes': 23,
      'target': 60,
      'new': 4,
      'new_cap': 10,
    });
    stream = FakeStream();
  });

  testWidgets('a build without identifiers says so', (tester) async {
    const empty = FirebaseConfig(
      apiKey: '',
      databaseUrl: '',
      syncUid: '',
      serverClientId: 'x',
    );
    await tester.pumpWidget(
      TutorApp(config: empty, open: () async => services(db, stream)),
    );
    expect(find.textContaining('write_firebase_config'), findsOneWidget);
  });

  testWidgets('open failure is shown', (tester) async {
    await tester.pumpWidget(
      TutorApp(config: _config, open: () async => throw StateError('boom')),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('boom'), findsOneWidget);
  });

  testWidgets('sign in -> Home with presence, due count and subjects', (
    tester,
  ) async {
    final s = services(db, stream);
    await tester.pumpWidget(TutorApp(config: _config, open: () async => s));
    await tester.pumpAndSettle();
    // Not Android in tests: the platform gate hides the button.
    expect(find.textContaining('Desktop sign-in'), findsOneWidget);
    await s.auth.signInWithGoogle(tokenFetcher: () async => 'g');
    await tester.pumpWidget(
      TutorApp(config: _config, open: () async => s, key: UniqueKey()),
    );
    await tester.pumpAndSettle();
    expect(find.text('How a car works'), findsOneWidget);
    expect(find.text('0 due for review'), findsOneWidget);
    expect(find.text('PC: checking'), findsOneWidget);
    stream.listens[Paths.workers]!
      ..add(const RtdbConnected())
      ..add(const RtdbPut('/', null));
    await tester.pumpAndSettle();
    expect(find.text('PC offline'), findsOneWidget);
    stream.listens[Paths.workers]!.add(const RtdbPut('/w', {'beat': 1}));
    await tester.pumpAndSettle();
    expect(find.text('PC online'), findsOneWidget);

    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(find.text('How a car works'), findsOneWidget);

    await tester.tap(find.byTooltip('Sign out'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Desktop sign-in'), findsOneWidget);
  });

  testWidgets('Home shows load errors and the offline banner', (tester) async {
    final s = services(db, stream);
    await s.auth.signInWithGoogle(tokenFetcher: () async => 'g');
    db.offline = true;
    await tester.pumpWidget(TutorApp(config: _config, open: () async => s));
    await tester.pumpAndSettle();
    expect(find.textContaining('Could not load'), findsOneWidget);
    db.offline = false;
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    db.offline = true;
    await tester.tap(find.byTooltip('Refresh'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Offline'), findsOneWidget);
  });

  testWidgets('sign-in button: cancel, wrong account, success', (tester) async {
    var signedIn = 0;
    Future<void> pump(TutorServices s, Future<String?> Function() fetch) =>
        tester.pumpWidget(
          MaterialApp(
            home: SignInScreen(
              services: s,
              onSignedIn: () => signedIn++,
              supported: true,
              tokenFetcher: fetch,
            ),
          ),
        );
    await pump(services(db, stream), () async => null);
    await tester.tap(find.text('Sign in with Google'));
    await tester.pumpAndSettle();
    expect(find.text('Sign-in cancelled.'), findsOneWidget);

    await pump(services(db, stream, uid: 'other'), () async => 'g');
    await tester.tap(find.text('Sign in with Google'));
    await tester.pumpAndSettle();
    expect(find.textContaining('wrong account'), findsOneWidget);

    await pump(services(db, stream), () async => 'g');
    await tester.tap(find.text('Sign in with Google'));
    await tester.pumpAndSettle();
    expect(signedIn, 1);
  });
}
