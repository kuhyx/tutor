// build-mobile-app R7: Today and Start fit one Pixel 6a screen.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/ui/start_screen.dart';
import 'package:tutor/ui/today_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/services.dart';

Map<String, Object?> _wire({int done = 0, int steps = 6}) => {
  'date': '2026-11-03',
  'steps': [
    for (var i = 1; i <= steps; i++)
      {
        'id': 's$i',
        'title': 'Step title $i, long enough to wrap onto a second line',
        'what': 'Do thing $i. ${'More detail about what to do. ' * 8}',
        'kind': 'coach',
        'target': 'slug-$i',
        'done': i <= done,
      },
  ],
  'current': done < steps ? 's${done + 1}' : null,
};

void main() {
  for (final done in [0, 6]) {
    fitTest('Today, $done done', (t, scale) async {
      pixelView(t, scale: scale);
      final s = services(FakeRtdb(), FakeStream());
      addTearDown(s.focus.dispose);
      await pumpFit(
        t,
        TodayScreen(
          services: s,
          plan: TodayPlan.fromJson(_wire(done: done)),
          openHome: () {},
        ),
        settle: false,
      );
      expectFits(t, state: 'done $done');
      expectReachable(t, find.byKey(const ValueKey('today-home')));
      if (done == 0) {
        expectReachable(t, find.byKey(const ValueKey('today-start')));
      }
    });
  }

  fitTest('Start while deciding', (t, scale) async {
    pixelView(t, scale: scale);
    final s = services(FakeRtdb(), FakeStream());
    addTearDown(s.focus.dispose);
    await pumpFit(
      t,
      StartScreen(services: s, onSignedOut: () {}),
      settle: false,
    );
    expectFits(t, state: 'deciding');
    // No plan within the wait: Home.
    await t.pump(const Duration(seconds: 7));
    await t.pumpAndSettle();
    expectFits(t, state: 'home');
  });
}
