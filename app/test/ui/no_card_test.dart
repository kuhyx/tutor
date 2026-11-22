// The Session's no-card state: one glyph that speaks the subject title and
// the next step, never the slug, and no "Review <module>" button (kuhy,
// 2026-11-22: the gate review opens by itself, see gate_flow_test).
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/relay_cue.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

void main() {
  testWidgets('no card left, no gate cards (older worker): one glyph', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'fuel-spark', at: fixtureNow),
    );
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      settle: false,
    );
    await sent(t);
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      error: 'no open card left in car',
      extra: {
        'subject_title': 'How a car works',
        'next': 'review_module',
        'module': 'fuel',
        'module_title': 'Fuel and ignition',
      },
      settle: false, // the empty chat's spinner never settles
    );
    expect(
      bySpoken('No card left to teach in How a car works', prefix: true),
      findsOneWidget,
    );
    expect(bySpoken('left in car', prefix: true), findsNothing);
    expect(controlByLabel('Review Fuel and ignition'), findsNothing);
    expect(controlByLabel('Review: Fuel and ignition'), findsNothing);
  });

  testWidgets('no card left, reviews due later: a ring, no button', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, subject: 'car', resume: true),
      settle: false,
    );
    await sent(t);
    final due = DateTime.now().add(const Duration(days: 400));
    await answer(
      t,
      db,
      stream,
      code: 'no_card_left',
      extra: {'next': 'reviews_due', 'due_at': due.millisecondsSinceEpoch},
      settle: false,
    );
    expect(find.byType(DueRing), findsOneWidget);
    expect(glyphsLabelled('Review Fuel and ignition'), findsNothing);
  });
}
