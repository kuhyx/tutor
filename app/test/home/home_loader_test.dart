import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';

const _me = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _t0 = 1791731346000;

Map<String, Object> _card(int rev, {bool suspended = false}) => {
  'module': 'm',
  'order': 1,
  'front': 'f',
  'back': 'b',
  'source': 'https://x',
  'excerpt': 'e',
  'rev': rev,
  'origin': 'seed',
  'suspended': suspended,
};

Map<String, Object> _meta(String title) => {
  'title': title,
  'status': 'active',
  'created': 1,
  'rev': 1,
  'origin': 'seed',
};

void main() {
  late FakeRtdb db;
  late MemoryKv kv;
  late EventLog events;
  late HomeLoader home;

  setUp(() {
    db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1', {
        'meta': {'schema': 1, 'min_client': 1},
        'rev': {'catalog': 3, 'stats': 1},
        'prefs': {'current_subject': 'car'},
        'live': {'session': '20261012-170448-5b71', 'subject': 'car'},
        'stats': {
          'today': {
            'day': '2026-10-12',
            'credited_minutes': 5,
            'target': 60,
            'new': 1,
            'new_cap': 10,
          },
        },
        'subjects': {
          'car': {
            'meta': _meta('How a car works'),
            'cards': {'eng': _card(1), 'old': _card(1, suspended: true)},
          },
          'automation': {
            'meta': _meta('Automation'),
            'cards': {'ld': _card(2)},
          },
          'drafting': {
            'plan': {'rev': 1, 'status': 'draft'},
          },
        },
      });
    kv = MemoryKv();
    events = EventLog(
      client: db.client(),
      kv: kv,
      dev: _me,
      ulid: UlidGenerator(),
    );
    home = HomeLoader(
      client: db.client(),
      kv: kv,
      events: events,
      now: () => DateTime.fromMillisecondsSinceEpoch(_t0 + 400 * 86400000),
    );
  });

  Future<void> teach(String s, String c) =>
      events.record(TaughtEvent(subject: s, card: c, at: _t0));

  test('subjects by title, due count, today; catalog cached by rev', () async {
    await teach('car', 'eng');
    await teach('car', 'old'); // suspended: not due
    await teach('automation', 'ld');
    final snap = await home.load();
    expect(snap.subjects.map((s) => s.id), ['automation', 'car']);
    expect(snap.due, 2);
    expect(snap.offline, isFalse);
    expect(snap.today!.creditedMinutes, 5);
    expect(snap.currentSubject, 'car');
    expect(snap.live!.session, '20261012-170448-5b71');
    expect(snap.subjects.last.data!.id, 'car');
    expect(await events.pending(), 0);

    db.log.clear();
    await home.load();
    expect(db.log.where((l) => l.contains('/subjects/')), isEmpty);

    db.root = setAt(db.root, 'tutor/v1/rev/catalog', 4);
    db.log.clear();
    await home.load();
    expect(db.log.where((l) => l.contains('/subjects/')), isNotEmpty);
  });

  test('offline: from cache; no cache: the error', () async {
    db.offline = true;
    await expectLater(home.load(), throwsA(isA<RtdbError>()));
    db.offline = false;
    await home.load();
    db.offline = true;
    await teach('car', 'eng');
    final snap = await home.load();
    expect(snap.offline, isTrue);
    expect(snap.today, isNull);
    expect(snap.due, 1);
    expect(await events.pending(), 1);
  });

  test('log sync failure still counts local events', () async {
    db.failPrefix = '/tutor/v1/log';
    await teach('car', 'eng');
    final snap = await home.load();
    expect(snap.due, 1);
    expect(await events.pending(), 1);
  });

  test('schema gate; absent meta, rev and stats are tolerated', () async {
    db.root = setAt(db.root, 'tutor/v1/meta/min_client', 2);
    await expectLater(
      home.load(),
      throwsA(
        isA<UnsupportedSchema>().having(
          (e) => e.toString(),
          'text',
          contains('too old'),
        ),
      ),
    );
    db.root = setAt(db.root, 'tutor/v1/meta', null);
    db.root = setAt(db.root, 'tutor/v1/rev', null);
    db.root = setAt(db.root, 'tutor/v1/stats', null);
    final snap = await home.load();
    expect(snap.today, isNull);
    expect(snap.subjects, hasLength(2));
    expect(HomeLoader(client: db.client(), kv: kv, events: events), isNotNull);
  });
}
