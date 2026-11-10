// build-mobile-app R7: the card editor and its form fit one Pixel 6a
// screen; with the keyboard up the field typed in and Save stay visible.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/editor_screen.dart';
import 'package:tutor/widgets/icon_field.dart';

import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

void main() {
  fitTest('Editor list, module, card form', (t, scale) async {
    pixelView(t, scale: scale);
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpFit(t, EditorScreen(services: s, subject: 'car'));
    expectFits(t, state: 'list');
    await t.tap(find.text('The four-stroke engine'));
    await t.pumpAndSettle();
    expectFits(t, state: 'module open');
    // Two taps: the module, then Add card (first in it on a phone).
    expectReachable(t, spoken('Add card'));
    await t.tap(spoken('Add card').hitTestable().first);
    await t.pumpAndSettle();
    expectFits(t, state: 'form');
    expectReachable(t, spoken('Save card'));
    for (final label in ['Front', 'Excerpt', 'Mnemonic']) {
      final field = find.descendant(
        of: find.byWidgetPredicate(
          (w) => w is FieldLabel && w.semanticLabel.startsWith(label),
        ),
        matching: find.byType(TextField),
      );
      await pageTo(t, field);
      await t.tap(field.hitTestable().first);
      pixelView(t, scale: scale, keyboard: fitKeyboard);
      await t.pumpAndSettle();
      expectFits(t, state: '$label + keyboard');
      expectReachable(t, spoken('Save card'), state: label);
      pixelView(t, scale: scale);
      await t.pumpAndSettle();
    }
  });
}
