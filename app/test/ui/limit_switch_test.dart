// The auto-switch (plan e79be0be-0 step 2): a `claude_unavailable` failure
// runs the outage chooser in the failed request's subject: due -> Review,
// else read mode, else the drill, else read mode's empty glyph.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/drill_view.dart';
import 'package:tutor/ui/read_screen.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/drill.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/read.dart';
import '../support/ui.dart';

/// A car card taught [ago] before the real now (a month: due).
Future<void> _taught(TutorServices s, Duration ago) => s.events.record(
  TaughtEvent(
    subject: 'car',
    card: 'eng-crank',
    at: DateTime.now().subtract(ago).millisecondsSinceEpoch,
  ),
);

/// Answers the chooser's `read_next` probe (it asks for the car only).
Future<void> _probe(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  final (_, req) = lastRequest(db);
  expect(req['kind'], 'read_next');
  expect(req['body'], {'subject': 'car'});
  await answer(t, db, stream, data: {'empty': true}, settle: false);
}

void main() {
  testWidgets('claude_unavailable with only taught cards opens the drill', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await _taught(s, Duration.zero);
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
    await _probe(t, db, stream);
    expect(bySpoken('Drill'), findsWidgets);
    expect(bySpoken('Claude limit — back at ${hhmm(kResetsAt)}'), findsOne);
    // It asks the PC for a question at once.
    expect(lastRequest(db).$2['kind'], 'drill_next');
  });

  testWidgets('a retried claude_unavailable opens the drill again', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await _taught(s, Duration.zero);
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
    await _probe(t, db, stream);
    expect(bySpoken('Drill'), findsWidgets);
    await t.pageBack();
    await t.pump(const Duration(seconds: 1));
    await t.pump(const Duration(seconds: 1)); // the route leaves after its fade
    expect(bySpoken('Drill'), findsNothing);
    await t.tap(controlByLabel('Retry'));
    await sent(t);
    await reply(t, db, stream, settle: false, limit);
    await sent(t);
    await _probe(t, db, stream);
    expect(bySpoken('Drill'), findsWidgets);
  });

  testWidgets('due cards of that subject open Review, with no probe', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await _taught(s, const Duration(days: 30));
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      size: kPhone,
      settle: false,
    );
    await sent(t);
    await answer(t, db, stream, code: 'claude_unavailable', settle: false);
    await t.pumpAndSettle();
    expect(find.byType(ReviewScreen), findsOneWidget);
    expect(find.byType(DrillView), findsNothing);
    expect(lastRequest(db).$2['kind'], 'session_start');
  });

  testWidgets('nothing taught: read mode, on that subject', (t) async {
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
    await answer(t, db, stream, code: 'claude_unavailable', settle: false);
    await sent(t);
    await answer(t, db, stream, data: readCard(), settle: false);
    expect(find.byType(ReadScreen), findsOneWidget);
    expect(lastRequest(db).$2['body'], {'subject': 'car'});
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
    expect(bySpoken('Drill'), findsNothing);
  });
}
