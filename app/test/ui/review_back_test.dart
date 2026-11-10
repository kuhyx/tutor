// Review's Back: the previous card again, revealed, with its earlier
// rating highlighted; re-rating replaces it (a review_undo + a new review).
// Backspace and Ctrl+Z do the same; Back works from the end screen too.
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/fake_stream.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

void main() {
  testWidgets('Back, Backspace and Ctrl+Z step back; re-rate replaces', (
    t,
  ) async {
    final db = fixtureDb();
    final s = await fixtureServices(db, FakeStream());
    final then = DateTime.fromMillisecondsSinceEpoch(fixtureNow);
    for (final c in ['eng-strokes', 'eng-crank']) {
      await s.events.record(
        TaughtEvent(
          subject: 'car',
          card: c,
          at: then.subtract(const Duration(days: 30)).millisecondsSinceEpoch,
        ),
      );
    }
    await pumpScreen(t, ReviewScreen(services: s, now: () => then));
    expect(spoken('Back'), findsNothing); // nothing rated yet
    final first = find.text('What does the crankshaft do?');
    expect(first, findsOneWidget);
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.digit3); // Good, by mistake
    await t.pumpAndSettle();
    expect(spoken('1 left'), findsOneWidget);

    await t.tap(spoken('Back'));
    await t.pumpAndSettle();
    expect(first, findsOneWidget);
    expect(spoken('2 left'), findsOneWidget);
    // Revealed, the earlier Good highlighted.
    expect(spoken('3 Good'), findsOneWidget);
    expect(gradeFilled(t, Grade.good), isTrue);
    expect(gradeFilled(t, Grade.again), isFalse);
    expect(spoken('Earlier: Good'), findsOneWidget);
    await t.tap(spoken('1 Again'));
    await t.pumpAndSettle();
    expect(spoken('1 left'), findsOneWidget);

    // The last card: rate, then Ctrl+Z from the end screen.
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.digit4);
    await t.pumpAndSettle();
    expect(spokenHas('All done'), findsOneWidget);
    expect(spoken('Back'), findsOneWidget);
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.keyZ);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await t.pumpAndSettle();
    expect(gradeFilled(t, Grade.easy), isTrue);
    // Backspace: back once more, to the first card (now Again).
    await t.sendKeyEvent(LogicalKeyboardKey.backspace);
    await t.pumpAndSettle();
    expect(first, findsOneWidget);
    expect(gradeFilled(t, Grade.again), isTrue);
    await t.tap(spoken('2 Hard'));
    await t.pumpAndSettle();

    final all = await s.events.all();
    expect(all.map((e) => e.event).whereType<ReviewUndoEvent>(), hasLength(3));
    // The fold sees only Hard on the first card, no rating on the second.
    final folded = fold(all, {
      'car/eng-crank': const CardInfo(rev: 2),
      'car/eng-strokes': const CardInfo(rev: 1),
    });
    expect(folded.reviewed, isEmpty);
  });
}
