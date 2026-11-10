import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/widgets/date_num.dart';

import '../support/no_words.dart';

void main() {
  test('numeric formats', () {
    final d = DateTime(2026, 11, 9, 7, 5);
    expect(dateNum(d), '11/09');
    expect(isoDate(d), '2026-11-09');
    expect(clockNum(d), '07:05');
    expect(minutesNum(5), '5');
    expect(minutesNum(65), '1:05');
  });

  test('due kind: overdue, today, later', () {
    final now = DateTime(2026, 11, 9, 12);
    expect(dueKindOf(DateTime(2026, 11, 8, 23), now), DueKind.overdue);
    expect(dueKindOf(DateTime(2026, 11, 9), now), DueKind.today);
    expect(dueKindOf(DateTime(2026, 11, 10), now), DueKind.later);
  });

  testWidgets('overdue is a red clock, today a filled dot, later nothing', (
    t,
  ) async {
    await t.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Column(
            children: [
              DueMark(DueKind.overdue),
              DueMark(DueKind.today),
              DueMark(DueKind.later),
            ],
          ),
        ),
      ),
    );
    final clock = t.widget<Icon>(find.byIcon(Icons.schedule));
    expect(clock.color, isNotNull);
    expect(find.byType(DecoratedBox), findsWidgets);
    expectNoWords(t, 'marks');
  });

  testWidgets('DueMark built at run time renders for every kind', (t) async {
    await t.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Column(children: [for (final k in DueKind.values) DueMark(k)]),
        ),
      ),
    );
    expect(find.byIcon(Icons.schedule), findsOneWidget);
  });
}
