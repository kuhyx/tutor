import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _live = 'tutor/v1/sessions/$fixtureLiveSid';

void main() {
  testWidgets('Continue in automation never shows the live car session', (
    t,
  ) async {
    // kuhy, 2026-10-12: live was a car session; Continue in automation
    // opened it. Now the screen asks for automation's open session.
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'automation', resume: true),
      settle: false,
    );
    await sent(t);
    stream.listens['tutor/v1/live']!.add(
      const RtdbPut('/', {'session': fixtureLiveSid, 'subject': 'car'}),
    );
    await t.pump();
    expect(
      stream.listens.keys,
      isNot(contains('tutor/v1/sessions/$fixtureLiveSid/meta')),
    );
    final start = await answer(
      t,
      db,
      stream,
      data: {'session': '20261012-180000-aaaa'},
      settle: false, // the new session's first turn is on its way
    );
    expect(start['kind'], 'session_start');
    expect(start['body'], {
      'subject': 'automation',
      'card': null,
      'resume': true,
      'device': 'desktop',
    });
    expect(
      stream.listens.keys,
      contains('tutor/v1/sessions/20261012-180000-aaaa/meta'),
    );
  });

  testWidgets('after Next card: day totals stay; the new card shows a wait', (
    t,
  ) async {
    // kuhy, 2026-10-12: Next card left an empty chat and "Active 0 min".
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    const next = '20261012-180000-aaaa';
    stream.listens['tutor/v1/live']!.add(
      const RtdbPut('/', {'session': next, 'subject': 'car'}),
    );
    await t.pump();
    const base = 'tutor/v1/sessions/$next';
    stream.listens['$base/meta']!.add(
      RtdbPut('/', {
        ...getAt(db.root, '$_live/meta')! as Map<String, dynamic>,
        'busy': null,
        'credited_minutes': 0,
        'clock': {'active_seconds': 0.0, 'reply_timeout_s': 600},
      }),
    );
    stream.listens['$base/msgs']!.add(const RtdbPut('/', null));
    await t.pump();
    await t.pump();
    expect(find.text('The tutor is preparing this card...'), findsOneWidget);
    expect(find.text('Start session'), findsNothing);
    expect(
      find.text('Today: 31 min active · credited 23/60 min'),
      findsOneWidget,
    );
    expect(find.text('This card: 0 min · credited 0'), findsOneWidget);
  });
}
