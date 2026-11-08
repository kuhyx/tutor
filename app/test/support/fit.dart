/// Phone-fit checks (build-mobile-app R7): a screen at Pixel 6a geometry
/// (411x914 dp, status bar and gesture-nav insets), at a font scale and with
/// an optional keyboard, must not scroll and must not overflow.
library;

import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/l10n/gen/app_localizations.dart';
import 'package:tutor/ui/ui_zoom.dart';

/// Pixel 6a density.
const fitDpr = 2.625;

/// Status bar (px).
const fitTopPx = 132.0;

/// Gesture nav inset (px).
const fitBottomPx = 63.0;

/// Pixel 6a screen (px).
const fitScreen = Size(1080, 2400);

/// The keyboard the fit tests open (dp).
const fitKeyboard = 330.0;

/// Font scales every screen must fit at.
const fitScales = [1.0, 1.15];

/// Sets Pixel 6a geometry, [scale] and a [keyboard] (dp) on the test view.
void pixelView(WidgetTester t, {double scale = 1, double keyboard = 0}) {
  t.view
    ..physicalSize = fitScreen
    ..devicePixelRatio = fitDpr
    ..padding = const FakeViewPadding(top: fitTopPx, bottom: fitBottomPx)
    ..viewInsets = FakeViewPadding(bottom: keyboard * fitDpr);
  t.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(t.view.reset);
  addTearDown(t.platformDispatcher.clearTextScaleFactorTestValue);
}

/// Pumps [screen] in a themed app; the caller set the view ([pixelView]).
Future<void> pumpFit(
  WidgetTester t,
  Widget screen, {
  bool settle = true,
}) async {
  await t.pumpWidget(
    MaterialApp(
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: buildLightTheme(),
      builder: (context, child) => UiZoomHost(child: child!),
      home: screen,
    ),
  );
  if (settle) {
    await t.pumpAndSettle();
  } else {
    for (var i = 0; i < 5; i++) {
      await t.pump(const Duration(milliseconds: 20));
    }
  }
}

/// Lowest y (dp) content may reach: above the keyboard or the nav inset.
double fitFloor(WidgetTester t) {
  final view = t.view;
  final bottom = view.viewInsets.bottom > view.padding.bottom
      ? view.viewInsets.bottom
      : view.padding.bottom;
  return (view.physicalSize.height - bottom) / view.devicePixelRatio;
}

/// No vertical Scrollable can scroll, except a text field's own; the
/// focused text field sits fully between the status bar and the keyboard
/// (or nav inset).
void expectFits(WidgetTester t, {String state = ''}) {
  final tag = state.isEmpty ? '' : ' [$state]';
  for (final s in t.stateList<ScrollableState>(find.byType(Scrollable))) {
    if (s.position.axis != Axis.vertical) continue;
    final inField = find
        .ancestor(
          of: find.byWidget(s.widget),
          matching: find.byType(EditableText),
        )
        .evaluate()
        .isNotEmpty;
    if (inField) continue;
    expect(
      s.position.maxScrollExtent,
      lessThanOrEqualTo(0),
      reason: 'scrolls$tag: ${s.widget.runtimeType} in ${s.context.widget}',
    );
  }
  const top = fitTopPx / fitDpr;
  final floor = fitFloor(t);
  for (final e in find.byType(EditableText).evaluate()) {
    // The field being typed in; others may sit on another page.
    if (!(e.widget as EditableText).focusNode.hasFocus) continue;
    final box = e.renderObject! as RenderBox;
    if (!box.attached || !box.hasSize) continue;
    final r = box.localToGlobal(Offset.zero) & box.size;
    expect(
      r.top,
      greaterThanOrEqualTo(top - 0.5),
      reason: 'field under bar$tag',
    );
    expect(
      r.bottom,
      lessThanOrEqualTo(floor + 0.5),
      reason: 'field hidden$tag',
    );
    // Not clipped away (another page) nor covered (a pinned bar).
    final hits = t.hitTestOnBinding(r.center).path.map((h) => h.target);
    expect(hits, contains(box), reason: 'field covered or off-page$tag');
  }
}

/// [f] is on screen and tappable above the keyboard or nav inset.
void expectReachable(WidgetTester t, Finder f, {String state = ''}) {
  final tag = state.isEmpty ? '' : ' [$state]';
  expect(f.hitTestable(), findsWidgets, reason: '$f not hit-testable$tag');
  final r = t.getRect(f.hitTestable().first);
  expect(
    r.top,
    greaterThanOrEqualTo(fitTopPx / fitDpr - 0.5),
    reason: '$f under bar$tag',
  );
  expect(
    r.bottom,
    lessThanOrEqualTo(fitFloor(t) + 0.5),
    reason: '$f hidden$tag',
  );
}

/// Runs [body] once per font scale in [fitScales], as its own test; a
/// [skip] reason names the todo item that owns the screen that cannot fit.
void fitTest(
  String name,
  Future<void> Function(WidgetTester t, double scale) body, {
  String? skip,
}) {
  for (final scale in fitScales) {
    final why = skip == null ? '' : ' (skipped: $skip)';
    testWidgets(
      '$name @ font $scale$why',
      (t) => body(t, scale),
      skip: skip != null,
    );
  }
}

/// Turns pages (next) until [f] is hit-testable; fails after [max] pages.
Future<void> pageTo(WidgetTester t, Finder f, {int max = 30}) async {
  for (var i = 0; i < max; i++) {
    if (f.hitTestable().evaluate().isNotEmpty) return;
    final next = find.byKey(const ValueKey('fit-next')).hitTestable();
    expect(next, findsWidgets, reason: '$f not on any page');
    await t.tap(next.last);
    await t.pumpAndSettle();
  }
  fail('$f not within $max pages');
}
