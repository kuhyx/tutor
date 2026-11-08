// build-mobile-app R7: Review fits one Pixel 6a screen in every state.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/log_event.dart';
import 'package:tutor/ui/review_screen.dart';

import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/ui.dart';

void main() {
  fitTest('Review front, back, flag, done', (t, scale) async {
    pixelView(t, scale: scale);
    final s = await fixtureServices(fixtureDb(), FakeStream());
    final then = DateTime.fromMillisecondsSinceEpoch(fixtureNow);
    await s.events.record(
      TaughtEvent(
        subject: 'car',
        card: 'eng-strokes',
        at: then.subtract(const Duration(days: 30)).millisecondsSinceEpoch,
      ),
    );
    await pumpFit(t, ReviewScreen(services: s, now: () => then));
    expectFits(t, state: 'front');
    expectReachable(t, find.text('Show answer (Space)'));
    await t.tap(find.text('Show answer (Space)'));
    await t.pumpAndSettle();
    expectFits(t, state: 'back');
    expectReachable(t, find.text('3 Good'));
    await t.tap(find.text('Flag (F)'));
    await t.pumpAndSettle();
    pixelView(t, scale: scale, keyboard: fitKeyboard);
    await t.pumpAndSettle();
    expectFits(t, state: 'flag + keyboard');
    expectReachable(t, find.widgetWithText(FilledButton, 'Flag'));
    await t.tap(find.widgetWithText(FilledButton, 'Flag'));
    pixelView(t, scale: scale);
    await t.pumpAndSettle();
    // Flagging retires the only card.
    expect(find.text('All done'), findsOneWidget);
    expectFits(t, state: 'done');
  });

  fitTest('Review nothing due', (t, scale) async {
    pixelView(t, scale: scale);
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await pumpFit(t, ReviewScreen(services: s));
    expectFits(t, state: 'empty');
  });
}
