// The phone keyboard opening: header and feed hidden, and the
// composer (focus, step, typed text) surviving the layout change.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/ui/session/composer.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';
import '../support/label_finders.dart';

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('phone, keyboard open: no header, no feed, same text scale', (
    t,
  ) async {
    await openComposer(t, phone: true);
    expect(bySpoken('This card:', prefix: true), findsOneWidget);
    expect(rich('Good. Now three quick ones'), findsOneWidget);
    double scale() =>
        MediaQuery.of(t.element(find.byType(Composer))).textScaler.scale(1);
    expect(scale(), 1);

    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(bySpoken('This card:', prefix: true), findsNothing);
    expect(bySpoken('Today:', prefix: true), findsNothing);
    // The question takes the feed's room (no folded tile over boxes).
    expect(rich('Good. Now three quick ones'), findsNothing);
    expect(find.byType(CollapsedTile), findsNothing);
    // Density is fixed (13 sp), no extra shrink on top.
    expect(scale(), 1);
    expect(bySpoken('1/3'), findsOneWidget);

    t.view.resetViewInsets();
    await t.pumpAndSettle();
    expect(bySpoken('This card:', prefix: true), findsOneWidget);
    expect(rich('Good. Now three quick ones'), findsOneWidget);
  });

  testWidgets('phone: the keyboard opening keeps focus, step and text', (
    t,
  ) async {
    await openComposer(t, phone: true);
    await t.tap(controlByLabel('Next')); // 2/3
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
    expect(bySpoken('2/3'), findsOneWidget);
    expect(boxText(t), 'half typed');
    expect(focused(), isTrue); // a remount would have dropped it
    t.view.resetViewInsets();
    await t.pumpAndSettle();
    expect(boxText(t), 'half typed');
    expect(focused(), isTrue);
  });
}
