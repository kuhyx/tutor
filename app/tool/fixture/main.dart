// Screenshot build: the real app over an in-memory database (never the
// real RTDB). `?screen=/plan/garden` opens that route over Home. Car's
// drivetrain module goes generating -> ready (rev.catalog bump) 20 s after
// the app opens (`&bump=<s>` to change it): `?screen=/plan/car` shows the
// Plan screen updating by itself.
//
// Build: fvm flutter build web -t tool/fixture/main.dart \
//   -o build/web_fixture --base-href /app/
import 'package:crdt_sync/crdt_sync.dart'
    show FirebaseCredentials, InMemoryCredentialStore;
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rev_watcher.dart';
import 'package:tutor/ui/app.dart';
import 'package:tutor/util/ulid.dart';

import '../../test/support/fake_rtdb.dart';
import 'fixture_data.dart';
import 'fixture_live.dart';
import 'fixture_stream.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _config = FirebaseConfig(
  apiKey: 'fixture',
  databaseUrl: 'https://fake',
  syncUid: 'fixture',
  serverClientId: '',
);

Future<TutorServices> _open() async {
  final now = DateTime.now().millisecondsSinceEpoch;
  final db = FakeRtdb()
    ..root = fixtureGenerating(setAt(null, 'tutor/v1', fixtureTree(now)));
  // The older session's transcript: the live one's first turns, stopped.
  const live = 'tutor/v1/sessions/20261012-170448-5b71';
  const old = 'tutor/v1/sessions/20261011-090000-a1b2';
  db.root = setAt(db.root, '$old/msgs', getAt(db.root, '$live/msgs'));
  db.root = setAt(db.root, '$old/meta', {
    ...getAt(db.root, '$live/meta')! as Map<String, dynamic>,
    'stopped': true,
  });
  final store = InMemoryCredentialStore();
  await store.save(
    FirebaseCredentials(
      idToken: 'fixture',
      refreshToken: 'fixture',
      expiresAt: DateTime.now().add(const Duration(days: 1)),
    ),
  );
  final kv = MemoryKv();
  final client = db.client();
  final stream = FixtureStream(
    client,
    () => db.root,
    change: (
      after: fixtureBumpDelay(Uri.base.queryParameters),
      apply: () => db.root = fixtureCardsReady(db.root),
    ),
  );
  final ulid = UlidGenerator();
  final events = EventLog(client: client, kv: kv, dev: _dev, ulid: ulid);
  for (final c in fixtureTaught) {
    await events.record(
      TaughtEvent(subject: 'car', card: c, at: now - 30 * 86400000),
    );
  }
  // One of them recalled a day later: mastered in the cards view.
  await events.record(
    ReviewEvent(
      subject: 'car',
      card: fixtureTaught.first,
      at: now - 29 * 86400000,
      grade: Grade.good,
      rev: 1,
    ),
  );
  return TutorServices(
    config: _config,
    dev: _dev,
    kv: kv,
    auth: TutorAuth(config: _config, store: store),
    client: client,
    stream: stream,
    relay: RequestRelay(client: client, stream: stream, dev: _dev, ulid: ulid),
    presence: PresenceWatcher(stream),
    rev: RevWatcher(stream),
    events: events,
    home: HomeLoader(client: client, kv: kv, events: events),
    catalog: Catalog(client: client, kv: kv),
    history: HistoryRepo(client),
    feedback: FeedbackSender(client: client, dev: _dev, ulid: ulid),
  );
}

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    TutorApp(
      config: _config,
      open: _open,
      initialRoute: Uri.base.queryParameters['screen'],
    ),
  );
}
