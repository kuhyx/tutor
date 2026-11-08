// build-mobile-app R7: Mock start and result fit one Pixel 6a screen.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_result_screen.dart';
import 'package:tutor/mock/mock_start_screen.dart';
import 'package:tutor/mock/mock_test_screen.dart';
import 'package:tutor/ui/fit_pages.dart';

import '../support/fit.dart';
import '../support/ui.dart';
import 'mock_fixtures.dart';
import 'mock_support.dart';

void main() {
  late Rig rig;
  setUp(() => rig = Rig());

  fitTest('Mock start', (t, scale) async {
    pixelView(t, scale: scale);
    await pumpFit(t, MockStartScreen(services: rig.s, links: rig.links));
    expectFits(t, state: 'start');
    expectReachable(t, find.byKey(const ValueKey('start')));
    // A malformed paper: its problem shows under Start.
    await t.tap(find.byKey(const ValueKey('start')));
    await t.pump(const Duration(milliseconds: 100));
    await answer(t, rig.db, rig.stream, data: {'mock_id': 'x'});
    expectFits(t, state: 'problem');
  });

  fitTest('Mock result pages', (t, scale) async {
    pixelView(t, scale: scale);
    final m = rig.session()..finished(resultData);
    await pumpFit(
      t,
      MockResultScreen(services: rig.s, session: m, links: rig.links),
    );
    expectFits(t, state: 'result');
    expectReachable(t, find.byKey(const ValueKey('done')));
  });

  // Tasks 0-1 are MCQ, 2 Python code, 3 SQL (mock_fixtures paperData).
  for (final i in [0, 2, 3]) {
    fitTest('Mock test task $i', (t, scale) async {
      await rig.pumpTest(t);
      pixelView(t, scale: scale);
      await t.pumpAndSettle();
      await t.tap(find.byKey(ValueKey('nav-$i')));
      await t.pumpAndSettle();
      expectFits(t, state: 'task $i');
      if (i == 0) {
        expectReachable(t, find.byKey(const ValueKey('opt-0')));
        return;
      }
      await t.tap(find.byKey(const ValueKey('sql-editor')).hitTestable());
      pixelView(t, scale: scale, keyboard: fitKeyboard);
      await t.pumpAndSettle();
      expectFits(t, state: 'task $i + keyboard');
      expectReachable(t, find.byKey(const ValueKey('run')), state: 'kb');
      expectReachable(t, find.byKey(const ValueKey('submit')), state: 'kb');
    });
  }

  // Desktop keeps its one scrolling list: no phone paging.
  testWidgets('Mock result and task on desktop', (t) async {
    final m = rig.session()..finished(resultData);
    await pumpScreen(
      t,
      MockResultScreen(services: rig.s, session: m, links: rig.links),
    );
    expect(find.byType(FitPages), findsNothing);
    expect(find.byType(ListView), findsWidgets);
    await pumpScreen(
      t,
      MockTestScreen(services: rig.s, session: rig.session(), links: rig.links),
    );
    await t.tap(find.byKey(const ValueKey('nav-3')));
    await t.pumpAndSettle();
    expect(find.byType(FitPages), findsNothing);
    expect(
      find.descendant(
        of: find.byKey(const ValueKey('task-list')),
        matching: find.byType(ListView),
      ),
      findsOneWidget,
    );
  });
}
