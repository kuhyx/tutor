import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/event_log.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_client.dart';
import 'package:tutor/util/ulid.dart';

import '../support/fake_rtdb.dart';

const _me = '0b6f2c1e-8f2a-4c1d-9e3b-7a5d4c3b2a10';
const _pc = '1c7a3d2f-9a3b-4d2e-8f4c-8b6e5d4c3b21';

ReviewEvent _review(int at, [Grade g = Grade.good]) =>
    ReviewEvent(subject: 'car', card: 'eng', at: at, grade: g, rev: 1);

void main() {
  late FakeRtdb db;
  late MemoryKv kv;
  late EventLog log;
  var clock = 1000;

  setUp(() {
    db = FakeRtdb();
    kv = MemoryKv();
    log = EventLog(
      client: db.client(),
      kv: kv,
      dev: _me,
      ulid: UlidGenerator(now: () => clock++),
    );
  });

  test('offline: recorded events count at once and stay queued', () async {
    db.offline = true;
    final a = await log.record(_review(1));
    final b = await log.record(_review(2));
    expect(a.eid.compareTo(b.eid), lessThan(0));
    expect(await log.pending(), 2);
    expect((await log.all()).map((e) => e.eid), containsAll([a.eid, b.eid]));
    await expectLater(log.flush(), throwsA(isA<RtdbError>()));
    expect(await log.pending(), 2);
  });

  test(
    'flush PUTs in eid order to the own subtree; retry is idempotent',
    () async {
      final a = await log.record(_review(1));
      final b = await log.record(_review(2, Grade.hard));
      expect(await log.flush(), 2);
      expect(db.log, [
        'PUT /tutor/v1/log/$_me/${a.eid}',
        'PUT /tutor/v1/log/$_me/${b.eid}',
      ]);
      expect(getAt(db.root, 'tutor/v1/log/$_me/${b.eid}/r'), 2);
      expect(await log.pending(), 0);
      expect(await log.flush(), 0);
      expect(await log.all(), hasLength(2));
    },
  );

  test('pull fetches each device after its cursor; skips junk', () async {
    db.root = setAt(null, 'tutor/v1/log', {
      _pc: {
        '01JA0000000000000000000001': {
          'k': 'taught',
          's': 'car',
          'c': 'eng',
          'at': 5,
        },
        '01JA0000000000000000000002': {'k': 'bogus'},
      },
      'not-a-device': {'x': 1},
    });
    await log.pull();
    var all = await log.all();
    expect(all.single.dev, _pc);
    expect(all.single.event, isA<TaughtEvent>());
    expect(db.log.last, startsWith('GET /tutor/v1/log/$_pc'));

    db.root = setAt(db.root, 'tutor/v1/log/$_pc/01JA0000000000000000000003', {
      'k': 'untaught',
      's': 'car',
      'c': 'eng',
      'at': 6,
    });
    db.log.clear();
    await log.pull();
    all = await log.all();
    expect(all.map((e) => e.event.runtimeType), contains(UntaughtEvent));
    // Second pull sent the cursor.
    expect(db.log, hasLength(2));
  });

  test('pull of an empty or emptied device', () async {
    db.root = setAt(null, 'tutor/v1/log/$_pc', {
      '01JA0000000000000000000009': 1,
    });
    await kv.set('log.cursor.$_pc', '01JA000000000000000000000Z');
    await log.pull();
    expect(await log.all(), isEmpty);
  });
}
