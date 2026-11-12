// build-mobile-app R7: Home, Plan and Progress fit one Pixel 6a screen.
// No vertical Scrollable may scroll, and each screen's primary actions
// must be hit-testable between the status bar and the nav inset.
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/plan_screen.dart';
import 'package:tutor/ui/progress_screen.dart';
import 'package:tutor/ui/ui_zoom.dart';

import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

const _dpr = 2.625;
const _topPx = 132.0;
const _bottomPx = 63.0;
const _screen = Size(1080, 2400);

/// Pumps [screen] at Pixel 6a geometry (status bar + gesture nav insets).
Future<void> _pumpPixel(WidgetTester t, Widget screen) async {
  t.view
    ..physicalSize = _screen
    ..devicePixelRatio = _dpr
    ..padding = const FakeViewPadding(top: _topPx, bottom: _bottomPx);
  addTearDown(t.view.reset);
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: buildLightTheme(),
      builder: (context, child) => UiZoomHost(child: child!),
      home: screen,
    ),
  );
  await t.pumpAndSettle();
}

/// Every vertical Scrollable on screen has nothing to scroll.
void _expectNoVerticalScroll(WidgetTester t) {
  final states = t.stateList<ScrollableState>(find.byType(Scrollable));
  for (final s in states) {
    if (s.position.axis != Axis.vertical) continue;
    expect(
      s.position.maxScrollExtent,
      lessThanOrEqualTo(0),
      reason:
          'vertical scroll in ${s.widget.runtimeType} under '
          '${s.context.widget}',
    );
  }
}

/// [f] is tappable and sits between the status bar and the nav inset.
void _expectTappable(WidgetTester t, Finder f) {
  expect(f.hitTestable(), findsOneWidget, reason: '$f not hit-testable');
  final r = t.getRect(f);
  final height = _screen.height / _dpr;
  expect(r.top, greaterThanOrEqualTo(_topPx / _dpr), reason: '$f under bar');
  expect(
    r.bottom,
    lessThanOrEqualTo(height - _bottomPx / _dpr),
    reason: '$f under the nav inset',
  );
}

void main() {
  testWidgets('Home fits one Pixel 6a screen', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await _pumpPixel(t, HomeScreen(services: s, onSignedOut: () {}));
    _expectNoVerticalScroll(t);
    _expectTappable(t, controlByLabel('Continue session'));
    _expectTappable(t, controlByLabel('Drill'));
    _expectTappable(t, find.text('How a car works'));
    _expectTappable(t, find.text('Vegetable gardening'));
    _expectTappable(t, controlByLabel('New subject'));
  });

  testWidgets('Plan fits one Pixel 6a screen', (t) async {
    final db = fixtureDb();
    db.root = setAt(db.root, 'tutor/v1-e2e/subjects/car/plan/history', [
      {'rev': 1, 'comment': 'less history', 'at': 1},
    ]);
    final s = await fixtureServices(db, FakeStream());
    await _pumpPixel(t, PlanScreen(services: s, subject: 'car'));
    _expectNoVerticalScroll(t);
    _expectTappable(t, chipSpoken('Modules'));
    _expectTappable(t, chipSpoken('Revisions'));
    _expectTappable(t, find.byKey(const ValueKey('module-tile-0')));
  });

  testWidgets('Progress fits one Pixel 6a screen', (t) async {
    final s = await fixtureServices(fixtureDb(), FakeStream());
    await _pumpPixel(t, ProgressScreen(services: s));
    _expectNoVerticalScroll(t);
    _expectTappable(t, chipSpoken('Minutes'));
    _expectTappable(t, chipSpoken('Taught'));
    _expectTappable(t, controlByLabel('All days'));
    _expectTappable(t, find.byKey(const ValueKey('subject-stat-0')));
  });
}
