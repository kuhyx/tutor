// Home's picked subject is offline-first: an offline pick reads back at once
// and a cold start with no network shows the last one pulled.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/home_loader.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/put_outbox.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';

const _root = 'tutor/v1-e2e';

FakeRtdb _db() => FakeRtdb()
  ..root = setAt(null, _root, {
    'meta': {'schema': 1, 'min_client': 1},
    'rev': {'catalog': 1},
    'prefs': {'current_subject': 'car'},
    'stats': {
      'today': {
        'day': '2026-10-12',
        'credited_minutes': 23,
        'target': 60,
        'new': 2,
        'new_cap': 10,
      },
    },
    'subjects': {
      'car': {
        'meta': {
          'title': 'Car',
          'status': 'active',
          'created': 1,
          'rev': 1,
          'origin': 'seed',
        },
      },
    },
  });

HomeLoader _home(FakeRtdb db, KvStore kv) {
  final client = db.client();
  final events = EventLog(
    client: client,
    kv: kv,
    dev: '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10',
    ulid: UlidGenerator(),
  );
  final box = PutOutbox(client, kv);
  return HomeLoader(client: client, kv: kv, events: events, outbox: box);
}

void main() {
  test('a cold start offline shows the last pulled subject', () async {
    final db = _db();
    final kv = MemoryKv();
    expect((await _home(db, kv).load()).currentSubject, 'car');
    db.offline = true;
    final cold = await _home(db, kv).load();
    expect(cold.offline, isTrue);
    expect(cold.currentSubject, 'car');
    expect(cold.today!.creditedMinutes, 23);
    // Progress was never opened: Home's sync kept `stats` for it anyway.
    expect((await fetchStats(db.client(), kv))!.today.target, 60);
  });

  test('an offline pick reads back at once and is pushed later', () async {
    final db = _db();
    final kv = MemoryKv();
    final home = _home(db, kv);
    await home.load();
    db.offline = true;
    await setCurrentSubject(home.outbox!, 'garden');
    expect((await home.load()).currentSubject, 'garden');
    db.offline = false;
    expect((await _home(db, kv).load()).currentSubject, 'garden');
    expect(getAt(db.root, '$_root/prefs/current_subject'), 'garden');
    home.outbox!.dispose();
  });

  test('a pick cleared on the database is not kept', () async {
    final db = _db();
    final kv = MemoryKv();
    await _home(db, kv).load();
    db.root = setAt(db.root, '$_root/prefs', null);
    expect((await _home(db, kv).load()).currentSubject, isNull);
    db.offline = true;
    expect((await _home(db, kv).load()).currentSubject, isNull);
  });
}
