// The Session's no-card state: the subject title and the next step, never
// the slug; "Review <module>" opens that module's review.
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('no card left -> Review <module> opens its review', (t) async {
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
      find.textContaining('No card left to teach in How a car works'),
      findsOneWidget,
    );
    expect(find.textContaining('left in car'), findsNothing);
    await t.tap(find.text('Review Fuel and ignition'));
    await sent(t);
    await sent(t);
    expect(find.text('Review: Fuel and ignition'), findsOneWidget);
    expect(find.text('What ignites the mixture?'), findsOneWidget);
  });

  testWidgets('no card left, reviews due: the time, no button', (t) async {
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
    final hh = due.hour.toString().padLeft(2, '0');
    final mm = due.minute.toString().padLeft(2, '0');
    expect(find.textContaining('Reviews due on'), findsOneWidget);
    expect(find.textContaining('at $hh:$mm.'), findsOneWidget);
    expect(find.textContaining(RegExp('^Review ')), findsNothing);
  });
}
