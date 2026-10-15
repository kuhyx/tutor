import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/drill.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('claude_unavailable in the Session opens the drill', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      size: kPhone,
      settle: false,
    );
    await sent(t);
    await reply(t, db, stream, settle: false, {
      'ok': false,
      'at': 1,
      'code': 'claude_unavailable',
      'error': 'limit',
      'resets_at': kResetsAt,
      'reason': 'five_hour_limit',
    });
    await sent(t);
    expect(find.text('Drill'), findsWidgets);
    expect(find.text('Claude limit — back at ${hhmm(kResetsAt)}'), findsOne);
    // It asks the PC for a question at once.
    expect(lastRequest(db).$2['kind'], 'drill_next');
  });

  testWidgets('a retried claude_unavailable opens the drill again', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      size: kPhone,
      settle: false,
    );
    await sent(t);
    final limit = {
      'ok': false,
      'at': 1,
      'code': 'claude_unavailable',
      'resets_at': kResetsAt,
      'retry': true,
    };
    await reply(t, db, stream, settle: false, limit);
    await sent(t);
    expect(find.text('Drill'), findsWidgets);
    await t.pageBack();
    await t.pump(const Duration(seconds: 1));
    await t.pump(const Duration(seconds: 1)); // the route leaves after its fade
    expect(find.text('Drill'), findsNothing);
    await t.tap(find.text('Retry'));
    await sent(t);
    await reply(t, db, stream, settle: false, limit);
    await sent(t);
    expect(find.text('Drill'), findsWidgets);
  });

  testWidgets('another failure does not open the drill', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      settle: false,
    );
    await sent(t);
    await answer(t, db, stream, code: 'model_error', settle: false);
    expect(find.text('Drill'), findsNothing);
  });
}
