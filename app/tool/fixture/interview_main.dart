// Interview focus screen over an in-memory database and a stand-in PC: the
// real FocusScreen and interview row, no Firebase, no live data. Build for
// the emulator or the phone (never installed over the real app id):
//
//   fvm flutter build apk -t tool/fixture/interview_main.dart ...
//
// The stand-in answers `focus_status` with an interview project and keeps
// each milestone's state: an evidence request marks it done, except a mock
// score above 100, which is a `focus_refused` (to see the error state).
import 'package:crdt_sync/crdt_sync.dart'
    show FirebaseCredentials, InMemoryCredentialStore;
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/config/firebase_config.dart';
import 'package:tutor/feedback/feedback_sender.dart';
import 'package:tutor/history/history.dart';
import 'package:tutor/home/catalog.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/json.dart';
import 'package:tutor/presence/client_beacon.dart';
import 'package:tutor/presence/presence_watcher.dart';
import 'package:tutor/relay/request_relay.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/auth.dart';
import 'package:tutor/sync/rev_watcher.dart';
import 'package:tutor/ui/focus_screen.dart';
import 'package:tutor/ui/ui_zoom.dart';
import 'package:tutor/util/ulid.dart';

import '../../test/support/fake_rtdb.dart';
import 'fixture_stream.dart';

const _dev = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _config = FirebaseConfig(
  apiKey: 'fixture',
  databaseUrl: 'https://fake',
  syncUid: 'fixture',
  serverClientId: '',
);

String _day(DateTime d) => d.toIso8601String().substring(0, 10);

/// The stand-in PC: one interview project whose milestone states move.
class _StandIn {
  new() {
    final today = DateTime.now();
    _test = DateTime(today.year, today.month, today.day + 10, 10);
    final sat = today.add(
      Duration(days: (DateTime.saturday - today.weekday) % 7),
    );
    _states = {
      'rules': 'late_done',
      'trip_ask:${_day(sat)}': 'pending',
      'phone:${_day(sat)}': 'pending',
      'mock': 'missed',
      'slot': 'pending',
    };
    _due = {
      'rules': today,
      'trip_ask:${_day(sat)}': today.add(const Duration(days: 2)),
      'phone:${_day(sat)}': today.add(const Duration(days: 4)),
      'mock': today,
      'slot': _test.subtract(const Duration(days: 1)),
    };
  }

  late final DateTime _test;
  late final Map<String, String> _states;
  late final Map<String, DateTime> _due;

  Json block() => {
    'milestones': [
      for (final e in _states.entries)
        {
          'id': e.key,
          'due': _due[e.key]!.toIso8601String().substring(0, 19),
          'state': e.value,
        },
    ],
    'missed': _states.values.any((s) => s == 'missed'),
    'trips': <Object>[],
    'weekend_answers': <String, Object>{},
  };

  Json status() {
    final project = {
      'id': 'acme-interview',
      'name': 'Acme interview',
      'start': _day(DateTime.now()),
      'end': _day(_test),
      'days_left': 10,
      'replaces': ['leetcode'],
      'daily_minutes': 30,
      'unlock_minutes': 30,
      'subjects': <String>[],
      'site_patterns': <String>[],
      'minutes': 12,
      'kind': 'interview',
      'test_at': _test.toIso8601String().substring(0, 19),
      'invite_url': 'https://app.codility.com/c/acme',
      'trips': <Object>[],
      'weekend_answers': <String, Object>{},
      ...block(),
    };
    return {
      'day': _day(DateTime.now()),
      'active': project,
      'projects': [project],
      'gates': [
        {'id': 'leetcode', 'label': 'LeetCode', 'replaceable': true},
      ],
      'subjects': <Object>[],
    };
  }

  Json answer(String kind, Json body) {
    Json ok(Json data) => {'ok': true, 'at': 1, 'data': data};
    switch (kind) {
      case 'focus_status':
        return ok(status());
      case 'focus_evidence':
        final value = body['value'];
        if (body['kind'] == 'score' && value is num && value > 100) {
          return {
            'ok': false,
            'at': 1,
            'code': 'focus_refused',
            'error': 'score is a percentage',
          };
        }
        final id = body['milestone']! as String;
        if (body['kind'] != 'slot') _states[id] = 'done';
        return ok(block());
      default:
        return ok(block());
    }
  }
}

Future<TutorServices> _open() async {
  final db = FakeRtdb();
  final kv = MemoryKv();
  final store = InMemoryCredentialStore();
  await store.save(
    FirebaseCredentials(
      idToken: 'fixture',
      refreshToken: 'fixture',
      expiresAt: DateTime.now().add(const Duration(days: 1)),
    ),
  );
  final client = db.client();
  final standIn = _StandIn();
  final stream = FixtureStream(client, () => db.root, worker: standIn.answer);
  final ulid = UlidGenerator();
  final events = EventLog(client: client, kv: kv, dev: _dev, ulid: ulid);
  return TutorServices(
    config: _config,
    dev: _dev,
    kv: kv,
    auth: TutorAuth(config: _config, store: store),
    client: client,
    stream: stream,
    relay: RequestRelay(client: client, stream: stream, dev: _dev, ulid: ulid),
    presence: PresenceWatcher(stream),
    beacon: ClientBeacon(client: client, dev: _dev, platform: 'android'),
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
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: buildLightTheme(),
      builder: (context, child) => UiZoomHost(child: child!),
      home: FutureBuilder<TutorServices>(
        future: _open(),
        builder: (context, snap) =>
            snap.hasData ? FocusScreen(services: snap.data!) : const Scaffold(),
      ),
    ),
  );
}
