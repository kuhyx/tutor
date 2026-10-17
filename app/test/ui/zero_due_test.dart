// Nothing due: no "Review (0 due)" anywhere, neither Home's global one nor
// a subject's (a module review, "Review <module>", is not due-based).
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('Home: 0 due hides Review; module review stays', (t) async {
    final db = fixtureDb();
    final s = await fixtureServices(db, FakeStream());
    // Taught just now (Home's clock is the real one): not due yet.
    final now = DateTime.now().millisecondsSinceEpoch;
    await s.events.record(
      TaughtEvent(subject: 'car', card: 'fuel-spark', at: now),
    );
    await pumpScreen(t, HomeScreen(services: s, onSignedOut: () {}));
    expect(find.textContaining('due)'), findsNothing);
    expect(find.text('Drill'), findsOneWidget);
    // Not due-based: a done module still offers its review.
    expect(find.text('Review Fuel and ignition'), findsOneWidget);
  });

  testWidgets('a block with 0 due: no Review this subject', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
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
      code: 'daily_new_cap',
      extra: const {'due_in_subject': 0, 'new_today': 25},
      settle: false,
    );
    expect(find.text('Learn more anyway'), findsOneWidget);
    expect(find.textContaining('Review this subject'), findsNothing);
  });
}
