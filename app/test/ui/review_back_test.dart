// Review's Back: the previous card again, revealed, with its earlier
// rating highlighted; re-rating replaces it (a review_undo + a new review).
// Backspace and Ctrl+Z do the same; Back works from the end screen too.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/log/fsrs_fold.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/fake_stream.dart';
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
    expect(find.text('Back'), findsNothing); // nothing rated yet
    final first = find.text('What does the crankshaft do?');
    expect(first, findsOneWidget);
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.digit3); // Good, by mistake
    await t.pumpAndSettle();
    expect(find.textContaining('1 left'), findsOneWidget);

    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(first, findsOneWidget);
    expect(find.textContaining('2 left'), findsOneWidget);
    // Revealed, the earlier Good highlighted.
    expect(find.text('3 Good'), findsOneWidget);
    expect(find.widgetWithText(FilledButton, '3 Good'), findsOneWidget);
    expect(find.text('Earlier: Good'), findsOneWidget);
    await t.tap(find.text('1 Again'));
    await t.pumpAndSettle();
    expect(find.textContaining('1 left'), findsOneWidget);

    // The last card: rate, then Ctrl+Z from the end screen.
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.digit4);
    await t.pumpAndSettle();
    expect(find.text('All done'), findsOneWidget);
    expect(find.text('Back'), findsOneWidget);
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.keyZ);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await t.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, '4 Easy'), findsOneWidget);
    // Backspace: back once more, to the first card (now Again).
    await t.sendKeyEvent(LogicalKeyboardKey.backspace);
    await t.pumpAndSettle();
    expect(first, findsOneWidget);
    expect(find.widgetWithText(FilledButton, '1 Again'), findsOneWidget);
    await t.tap(find.text('2 Hard'));
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
