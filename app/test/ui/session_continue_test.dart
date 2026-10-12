import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

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
    );
    expect(start['kind'], 'session_start');
    expect(start['body'], {
      'subject': 'automation',
      'card': null,
      'resume': true,
    });
    expect(
      stream.listens.keys,
      contains('tutor/v1/sessions/20261012-180000-aaaa/meta'),
    );
  });
}
