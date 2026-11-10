import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/numeric_date_picker.dart';

import '../support/no_words.dart';
import '../support/ui.dart';

final _today = DateTime(2026, 11, 2);
final DateTime _last = _today.add(const Duration(days: 365));

Finder _day(int d) => find.byWidgetPredicate((w) => w is DayCell && w.day == d);

DayCell _cell(WidgetTester t, int d) => t.widget<DayCell>(_day(d));

Finder _header(String digits) => find.descendant(
  of: find.byKey(NumericDatePicker.headerKey),
  matching: find.text(digits),
);

/// Pumps a button that opens the picker; the returned list gets its result.
Future<List<DateTime?>> _open(WidgetTester t, {DateTime? initial}) async {
  final results = <DateTime?>[];
  await pumpScreen(
    t,
    Scaffold(
      body: Builder(
        builder: (context) => IconButton(
          icon: const Icon(Icons.event),
          onPressed: () async => results.add(
            await showNumericDatePicker(
              context: context,
              initialDate: initial ?? DateTime(2026, 11, 5),
              firstDate: _today,
              lastDate: _last,
            ),
          ),
        ),
      ),
    ),
  );
  await t.tap(find.byIcon(Icons.event));
  await t.pumpAndSettle();
  return results;
}

Future<void> _tap(WidgetTester t, Finder f) async {
  await t.tap(f);
  await t.pumpAndSettle();
}

void main() {
  testWidgets('paints digits only: month, year, Monday-first grid', (t) async {
    await _open(t);
    expect(find.byType(NumericDatePicker), findsOneWidget);
    expectNoWords(t, 'numeric date picker');
    expect(_header('11'), findsOneWidget);
    expect(_header('2026'), findsOneWidget);
    // 2026-11-01 is a Sunday: last column of the first row, 2 starts row 2.
    final one = t.getCenter(_day(1));
    final two = t.getCenter(_day(2));
    final nine = t.getCenter(_day(9));
    expect(one.dx, greaterThan(two.dx));
    expect(one.dy, lessThan(two.dy));
    expect(nine.dx, two.dx);
    expect(t.getCenter(_day(8)).dx, one.dx);
    expect(find.byType(DayCell), findsNWidgets(30));
    expect(find.bySemanticsLabel('Confirm'), findsOneWidget);
    expect(find.bySemanticsLabel('Cancel'), findsOneWidget);
    expect(find.byType(Tooltip), findsNothing);
  });

  testWidgets('the selected day is highlighted; past days are dead', (t) async {
    await _open(t);
    expect(_cell(t, 5).selected, isTrue);
    expect(_cell(t, 6).selected, isFalse);
    expect(_cell(t, 1).enabled, isFalse);
    expect(_cell(t, 2).enabled, isTrue);
    await _tap(t, _day(1));
    expect(_cell(t, 1).selected, isFalse);
    expect(_cell(t, 5).selected, isTrue);
  });

  testWidgets('› and ‹ move months within the range only', (t) async {
    await _open(t);
    final prev = find.bySemanticsLabel('Previous month');
    final next = find.bySemanticsLabel('Next month');
    await _tap(t, prev);
    expect(_header('11'), findsOneWidget, reason: 'first month: ‹ is off');
    await _tap(t, next);
    expect(_header('12'), findsOneWidget);
    expect(find.byType(DayCell), findsNWidgets(31));
    expect(_cell(t, 1).enabled, isTrue);
    for (var i = 0; i < 11; i++) {
      await _tap(t, next);
    }
    expect(_header('11'), findsOneWidget);
    expect(_header('2027'), findsOneWidget);
    expect(_cell(t, 2).enabled, isTrue);
    expect(_cell(t, 3).enabled, isFalse);
    await _tap(t, next);
    expect(_header('2027'), findsOneWidget, reason: 'last month: › is off');
    expectNoWords(t, 'numeric date picker 2027-11');
  });

  testWidgets('a day then ✓ returns it', (t) async {
    final results = await _open(t);
    // Spoken as the whole date, so TalkBack and E2E can pick it.
    await _tap(t, find.bySemanticsLabel('2026-11-20'));
    expect(_cell(t, 20).selected, isTrue);
    await _tap(t, find.bySemanticsLabel('Confirm'));
    expect(find.byType(NumericDatePicker), findsNothing);
    expect(results, [DateTime(2026, 11, 20)]);
  });

  testWidgets('✕ returns nothing', (t) async {
    final results = await _open(t);
    await _tap(t, _day(20));
    await _tap(t, find.bySemanticsLabel('Cancel'));
    expect(find.byType(NumericDatePicker), findsNothing);
    expect(results, [null]);
  });

  testWidgets('an initial day outside the range opens on the nearest edge', (
    t,
  ) async {
    final results = await _open(t, initial: DateTime(2026, 10, 30));
    expect(_header('11'), findsOneWidget);
    expect(_cell(t, 2).selected, isTrue);
    await _tap(t, find.bySemanticsLabel('Confirm'));
    expect(results, [_today]);
  });
}
