import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/home/remote_bits.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/session/today_header.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rev_watcher.dart';
import 'package:tutor/sync/rtdb_event.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';

const Map<String, Object> _today = {
  'day': '2026-10-12',
  'credited_minutes': 23,
  'active_minutes': 31,
  'target': 60,
  'new': 2,
  'new_cap': 10,
};

Future<void> _tick() => Future<void>.delayed(Duration.zero);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('the header shows the day first, this card second', () {
    // kuhy, 2026-10-12: after Next card the header read "Active 0 min ·
    // credited 0" because the new card is a new session.
    final today = Today.fromJson(_today);
    expect(headerLines(today, activeSeconds: 59, sessionCredited: 0), (
      'Today: 31 min active · credited 23/60 min',
      'This card: 0 min · credited 0',
    ));
    final older = Today.fromJson({..._today}..remove('active_minutes'));
    expect(
      headerLines(older, activeSeconds: 125, sessionCredited: 2).$1,
      'Today: credited 23/60 min',
    );
    final carried = Today.fromJson({..._today, 'banked': 40, 'prepaid': 15});
    expect(
      headerLines(carried, activeSeconds: 0, sessionCredited: 0).$1,
      'Today: 31 min active · credited 23/60 min · Banked 40 min · prepaid 15',
    );
    final empty = Today.fromJson({..._today, 'banked': 0, 'prepaid': 0});
    expect(
      headerLines(empty, activeSeconds: 0, sessionCredited: 0).$1,
      'Today: 31 min active · credited 23/60 min',
    );
    expect(headerLines(null, activeSeconds: 125, sessionCredited: 2), (
      'Today: …',
      'This card: 2 min · credited 2',
    ));
  });

  test('reads stats.today now and on every rev.stats move', () async {
    final db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1-e2e/stats/today', _today);
    final stream = FakeStream();
    final rev = RevWatcher(stream);
    final feed = TodayFeed(client: db.client(), rev: rev, kv: MemoryKv())
      ..start()
      ..start(); // idempotent
    await _tick();
    await _tick();
    expect(feed.today.value!.activeMinutes, 31);
    db.root = setAt(db.root, 'tutor/v1-e2e/stats/today/active_minutes', 40);
    stream.listens['tutor/v1-e2e/rev']!
      ..add(const RtdbPut('/', {'stats': 1}))
      ..add(const RtdbPatch('/', {'stats': 2}));
    await _tick();
    await _tick();
    expect(feed.today.value!.activeMinutes, 40);
    db.offline = true;
    await feed.load(); // a failure keeps the last value
    expect(feed.today.value!.activeMinutes, 40);
    db
      ..offline = false
      ..root = setAt(db.root, 'tutor/v1-e2e/stats', null);
    await feed.load();
    expect(feed.today.value, isNull);
    await feed.dispose();
    await rev.dispose();
  });

  test('keeps stats.today and shows it offline after a restart', () async {
    final kv = MemoryKv();
    final db = FakeRtdb()
      ..root = setAt(null, 'tutor/v1-e2e/stats/today', _today);
    final rev = RevWatcher(FakeStream());
    final first = TodayFeed(client: db.client(), rev: rev, kv: kv);
    await first.load();
    expect(kv.data[kTodayCacheKey], isNotNull);
    await first.dispose();
    final offline = FakeRtdb()..offline = true;
    final second = TodayFeed(client: offline.client(), rev: rev, kv: kv);
    await second.load();
    expect(second.today.value!.creditedMinutes, 23);
    kv.data[kTodayCacheKey] = '{not json';
    final third = TodayFeed(client: offline.client(), rev: rev, kv: kv);
    await third.load(); // a broken copy is ignored
    expect(third.today.value, isNull);
    await second.dispose();
    await third.dispose();
    await rev.dispose();
  });

  test('a database without stats.today clears the kept copy', () async {
    final kv = MemoryKv();
    kv.data[kTodayCacheKey] = '{"day": "x"}';
    final db = FakeRtdb();
    final rev = RevWatcher(FakeStream());
    final feed = TodayFeed(client: db.client(), rev: rev, kv: kv);
    await feed.load();
    expect(kv.data.containsKey(kTodayCacheKey), isFalse);
    expect(feed.today.value, isNull);
    await feed.dispose();
    await rev.dispose();
  });
}
