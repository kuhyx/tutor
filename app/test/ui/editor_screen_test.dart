import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/editor_screen.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

void main() {
  testWidgets('modules -> cards; edit, add, flag', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      EditorScreen(services: s, subject: 'car'),
      size: const Size(800, 1600),
    );
    expect(find.text('3 cards · mastered'), findsOneWidget);
    expect(find.text('1 card · ready'), findsOneWidget);
    await t.tap(find.text('The four-stroke engine'));
    await t.pumpAndSettle();

    await t.tap(find.byTooltip('Flag').first);
    await t.pumpAndSettle();
    await t.enterText(find.byType(TextField), 'answer is wrong');
    await t.tap(find.widgetWithText(FilledButton, 'Flag'));
    await t.pumpAndSettle();
    final flags = (await s.events.all())
        .map((e) => e.event)
        .whereType<FlagEvent>();
    expect(flags.single.reason, 'answer is wrong');
    await t.tap(find.byTooltip('Flag').first);
    await t.pumpAndSettle();
    await t.tap(find.text('Cancel'));
    await t.pumpAndSettle();

    await t.tap(find.text('What are the four strokes?'));
    await t.pumpAndSettle();
    expect(find.text('Edit card'), findsOneWidget);
    await t.enterText(
      find.widgetWithText(TextField, 'Front (question, <=25 words)'),
      'Which four strokes?',
    );
    await t.enterText(
      find.widgetWithText(TextField, 'Requires (card ids, comma separated)'),
      'eng-crank, ',
    );
    await t.tap(find.text('Save card'));
    await sent(t);
    final edit = await answer(
      t,
      db,
      stream,
      data: {'card': 'eng-strokes', 'rev': 2},
    );
    expect(edit['body'], containsPair('card', 'eng-strokes'));
    expect(edit['body'], containsPair('requires', ['eng-crank']));
    expect(find.text('Edit cards'), findsOneWidget); // popped back

    await t.tap(find.text('Add card').first);
    await t.pumpAndSettle();
    expect(find.text('New card'), findsOneWidget);
    expect(find.textContaining('Front: 1-25 words'), findsOneWidget);
    expect(
      t
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Save card'))
          .onPressed,
      isNull,
    );
  });

  testWidgets('switch subject; nothing cached', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, EditorScreen(services: s));
    await t.tap(find.byType(DropdownButton<String>));
    await t.pumpAndSettle();
    await t.tap(find.text('Vegetable gardening').last);
    await t.pumpAndSettle();
    expect(find.text('0 cards · locked'), findsWidgets);
  });
}
