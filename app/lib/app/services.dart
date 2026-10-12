/// Wiring: one instance of each logic service per app run.
library;

import 'package:crdt_sync/crdt_sync.dart' show FirebaseCredentialStore;
import 'package:http/http.dart' as http;
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/device_id.dart';
import 'package:tutor/storage/kv_open.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/sync/rtdb_stream.dart';
import 'package:tutor/util/ulid.dart';

/// Everything the screens need.
class TutorServices {
  /// Creates the bundle (use [open]).
  new({
    required this.config,
    required this.dev,
    required this.kv,
    required this.auth,
    required this.client,
    required this.stream,
    required this.relay,
    required this.presence,
    required this.events,
    required this.home,
  });

  /// Opens the platform stores and builds every service. Tests inject
  /// [store], [kv] and [httpClient].
  static Future<TutorServices> open(
    FirebaseConfig config, {
    FirebaseCredentialStore? store,
    KvStore? kv,
    http.Client? httpClient,
  }) async {
    final kvStore = kv ?? await openKv();
    final dev = await loadDeviceId(kvStore);
    final auth = TutorAuth(
      config: config,
      store: store ?? secureCredentialStore(),
      httpClient: httpClient,
    );
    final client = RtdbClient(
      databaseUrl: config.databaseUrl,
      idToken: auth.idToken,
      httpClient: httpClient,
    );
    final stream = RtdbStream(client);
    final ulid = UlidGenerator();
    final events = EventLog(client: client, kv: kvStore, dev: dev, ulid: ulid);
    return TutorServices(
      config: config,
      dev: dev,
      kv: kvStore,
      auth: auth,
      client: client,
      stream: stream,
      relay: RequestRelay(client: client, stream: stream, dev: dev, ulid: ulid),
      presence: PresenceWatcher(stream),
      events: events,
      home: HomeLoader(client: client, kv: kvStore, events: events),
    );
  }

  /// Build-time Firebase identifiers.
  final FirebaseConfig config;

  /// This install's device id.
  final String dev;

  /// Per-install store.
  final KvStore kv;

  /// Firebase session.
  final TutorAuth auth;

  /// REST client.
  final RtdbClient client;

  /// SSE transport.
  final RtdbStream stream;

  /// Request relay.
  final RequestRelay relay;

  /// PC presence.
  final PresenceWatcher presence;

  /// Offline event log.
  final EventLog events;

  /// Home data.
  final HomeLoader home;
}
