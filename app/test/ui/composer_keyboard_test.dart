// The phone keyboard opening: header hidden, last line, 85% text, and the
// composer (focus, step, typed text) surviving the layout change.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/session/composer.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('phone, keyboard open: no header, last line, 85% text', (
    t,
  ) async {
    await openComposer(t, phone: true);
    expect(find.textContaining('This card:'), findsOneWidget);
    expect(rich('Good. Now three quick ones'), findsOneWidget);
    double scale() =>
        MediaQuery.of(t.element(find.byType(Composer))).textScaler.scale(1);
    expect(scale(), 1);

    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(find.textContaining('This card:'), findsNothing);
    expect(find.textContaining('Today:'), findsNothing);
    expect(rich('Good. Now three quick ones'), findsNothing);
    expect(rich('a guess is fine.'), findsOneWidget);
    expect(scale(), closeTo(0.85, 1e-9));
    // The question and its box are still there.
    expect(find.text('1/3'), findsOneWidget);

    await t.tap(find.byIcon(Icons.expand_more));
    await t.pumpAndSettle();
    expect(rich('Good. Now three quick ones'), findsOneWidget);

    t.view.resetViewInsets();
    await t.pumpAndSettle();
    expect(find.textContaining('This card:'), findsOneWidget);
    expect(scale(), 1);
  });

  testWidgets('phone: the keyboard opening keeps focus, step and text', (
    t,
  ) async {
    await openComposer(t, phone: true);
    await t.tap(find.text('Next')); // 2/3
    await t.pumpAndSettle();
    await t.tap(find.byType(TextField)); // focus the box
    await t.enterText(find.byType(TextField), 'half typed');
    await t.pump();
    bool focused() => t
        .widget<EditableText>(
          find.descendant(
            of: find.byType(TextField),
            matching: find.byType(EditableText),
          ),
        )
        .focusNode
        .hasFocus;
    expect(focused(), isTrue);
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(find.text('2/3'), findsOneWidget);
    expect(boxText(t), 'half typed');
    expect(focused(), isTrue); // a remount would have dropped it
    t.view.resetViewInsets();
    await t.pumpAndSettle();
    expect(boxText(t), 'half typed');
    expect(focused(), isTrue);
  });
}
