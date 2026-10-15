import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/stats.dart';
import 'package:tutor/session/today_header.dart';
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
    expect(headerLines(null, activeSeconds: 125, sessionCredited: 2), (
      'Today: …',
      'This card: 2 min · credited 2',
    ));
  });

  test('reads stats.today now and on every rev.stats move', () async {
    final db = FakeRtdb()..root = setAt(null, 'tutor/v1/stats/today', _today);
    final stream = FakeStream();
    final rev = RevWatcher(stream);
    final feed = TodayFeed(client: db.client(), rev: rev)
      ..start()
      ..start(); // idempotent
    await _tick();
    await _tick();
    expect(feed.today.value!.activeMinutes, 31);
    db.root = setAt(db.root, 'tutor/v1/stats/today/active_minutes', 40);
    stream.listens['tutor/v1/rev']!
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
      ..root = setAt(db.root, 'tutor/v1/stats', null);
    await feed.load();
    expect(feed.today.value, isNull);
    await feed.dispose();
    await rev.dispose();
  });
}
