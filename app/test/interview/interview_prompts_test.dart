import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/interview_prompts.dart';
import 'package:tutor/ui/interview_time_dialog.dart';
import 'package:tutor/ui/numeric_date_picker.dart';

final _first = DateTime(2026, 11, 10);
final _last = DateTime(2027, 11, 10);

Future<BuildContext> _open(WidgetTester t) async {
  late BuildContext ctx;
  await t.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (c) {
          ctx = c;
          return const SizedBox();
        },
      ),
    ),
  );
  return ctx;
}

Future<void> _tapDay(WidgetTester t, int day) async {
  await t.tap(find.text('$day').first);
  await t.pump();
  await t.tap(find.byIcon(Icons.check));
  await t.pumpAndSettle();
}

void main() {
  testWidgets('range: two numeric dates, no framework picker', (t) async {
    final ctx = await _open(t);
    final f = const MaterialPrompts().pickRange(
      ctx,
      first: _first,
      last: _last,
    );
    await t.pumpAndSettle();
    expect(find.byType(NumericDatePicker), findsOneWidget);
    await _tapDay(t, 12);
    expect(find.byType(NumericDatePicker), findsOneWidget);
    await _tapDay(t, 14);
    final r = await f;
    expect(r?.start, DateTime(2026, 11, 12));
    expect(r?.end, DateTime(2026, 11, 14));
  });

  testWidgets('range: dismissing either date gives null', (t) async {
    final ctx = await _open(t);
    var f = const MaterialPrompts().pickRange(ctx, first: _first, last: _last);
    await t.pumpAndSettle();
    await t.tap(find.byIcon(Icons.close));
    await t.pumpAndSettle();
    expect(await f, isNull);
    f = const MaterialPrompts().pickRange(ctx, first: _first, last: _last);
    await t.pumpAndSettle();
    await _tapDay(t, 12);
    await t.tap(find.byIcon(Icons.close));
    await t.pumpAndSettle();
    expect(await f, isNull);
  });

  testWidgets('date and time: digits for the clock', (t) async {
    final ctx = await _open(t);
    final f = const MaterialPrompts().pickDateTime(
      ctx,
      first: _first,
      last: _last,
    );
    await t.pumpAndSettle();
    await _tapDay(t, 20);
    await t.enterText(find.byKey(DigitTimePicker.hourKey), '14');
    await t.enterText(find.byKey(DigitTimePicker.minuteKey), '5');
    await t.pump();
    await t.tap(find.byKey(DigitTimePicker.okKey));
    await t.pumpAndSettle();
    expect(await f, DateTime(2026, 11, 20, 14, 5));
  });

  testWidgets('date and time: a bad clock cannot be confirmed', (t) async {
    final ctx = await _open(t);
    final f = const MaterialPrompts().pickDateTime(
      ctx,
      first: _first,
      last: _last,
    );
    await t.pumpAndSettle();
    await _tapDay(t, 20);
    for (final (h, m) in [('24', '00'), ('9', '60'), ('', '00')]) {
      await t.enterText(find.byKey(DigitTimePicker.hourKey), h);
      await t.enterText(find.byKey(DigitTimePicker.minuteKey), m);
      await t.pump();
      final ok = t.widget<IconButton>(find.byKey(DigitTimePicker.okKey));
      expect(ok.onPressed, isNull, reason: '$h:$m');
    }
    await t.tapAt(const Offset(2, 2)); // dismiss the dialog
    await t.pumpAndSettle();
    expect(await f, isNull);
  });

  testWidgets('date and time: dismissing the date gives null', (t) async {
    final ctx = await _open(t);
    final f = const MaterialPrompts().pickDateTime(
      ctx,
      first: _first,
      last: _last,
    );
    await t.pumpAndSettle();
    await t.tap(find.byIcon(Icons.close));
    await t.pumpAndSettle();
    expect(await f, isNull);
  });
}
