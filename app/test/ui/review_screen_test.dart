import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('front -> reveal -> rate by key and button; flag; done', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    final then = DateTime.fromMillisecondsSinceEpoch(fixtureNow);
    for (final c in ['eng-strokes', 'eng-crank', 'eng-valves']) {
      await s.events.record(
        TaughtEvent(
          subject: 'car',
          card: c,
          at: then.subtract(const Duration(days: 30)).millisecondsSinceEpoch,
        ),
      );
    }
    await pumpScreen(t, ReviewScreen(services: s, now: () => then));
    expect(find.textContaining('3 left'), findsOneWidget);
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    expect(find.textContaining('crankshaft revolution'), findsOneWidget);
    await t.sendKeyEvent(LogicalKeyboardKey.digit3);
    await t.pumpAndSettle();
    expect(find.textContaining('2 left'), findsOneWidget);
    await t.tap(find.text('Show answer (Space)'));
    await t.pumpAndSettle();
    await t.tap(find.text('1 Again'));
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.keyF);
    await t.pumpAndSettle();
    await t.enterText(find.byType(TextField), 'unclear');
    await t.tap(find.widgetWithText(FilledButton, 'Flag'));
    await t.pumpAndSettle();
    expect(find.text('All done'), findsOneWidget);
    final events = (await s.events.all()).map((e) => e.event).toList();
    expect(events.whereType<ReviewEvent>().map((e) => e.grade), [
      Grade.good,
      Grade.again,
    ]);
    expect(events.whereType<FlagEvent>().single.reason, 'unclear');
  });

  testWidgets('nothing due', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, ReviewScreen(services: s));
    expect(find.text('Nothing due'), findsOneWidget);
  });
}
