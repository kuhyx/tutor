// The phone layout switch (`isCompact`) and the paged "+" tile's
// accessibility box, which screenshot-driven phone taps rely on.
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/ui/home_fit.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/layout.dart';
import 'package:tutor/ui/ui_scale.dart';
import 'package:tutor/ui/ui_zoom.dart';

import '../support/fake_stream.dart';
import '../support/ui.dart';

/// Sizes the test window to [size] dp (DPR 1), reset after the test.
void _window(WidgetTester t, Size size) {
  t.view
    ..physicalSize = size
    ..devicePixelRatio = 1;
  addTearDown(t.view.reset);
}

/// `isCompact` in a [size] window.
Future<bool> _compactAt(WidgetTester t, Size size) async {
  _window(t, size);
  late bool compact;
  await t.pumpWidget(
    MediaQuery(
      data: MediaQueryData(size: size),
      child: Builder(
        builder: (context) {
          compact = isCompact(context);
          return const SizedBox();
        },
      ),
    ),
  );
  return compact;
}

/// `isCompact` inside the app's scaler: a [display] window at Display size
/// [zoom], as `MaterialApp.builder` wraps every screen.
Future<bool> _compactScaled(WidgetTester t, Size display, double zoom) async {
  _window(t, display);
  late bool compact;
  await t.pumpWidget(
    UiZoomHost(
      zoom: UiZoom(initial: zoom),
      child: MediaQuery(
        data: MediaQueryData(size: display),
        child: UiScale(
          display: display,
          child: Builder(
            builder: (context) {
              compact = isCompact(context);
              return const SizedBox();
            },
          ),
        ),
      ),
    ),
  );
  return compact;
}

/// [node]'s rect in logical screen coordinates (root DPR transform skipped).
Rect _globalRect(SemanticsNode node) {
  var rect = node.rect;
  for (SemanticsNode? n = node; n != null && n.parent != null; n = n.parent) {
    final m = n.transform;
    if (m != null) rect = MatrixUtils.transformRect(m, rect);
  }
  return rect;
}

void main() {
  testWidgets('isCompact: phones only, never a desktop window', (t) async {
    expect(await _compactAt(t, const Size(411, 914)), isTrue);
    expect(await _compactAt(t, const Size(599, 950)), isTrue);
    expect(await _compactAt(t, const Size(600, 914)), isFalse);
    expect(await _compactAt(t, const Size(411, 951)), isFalse);
    // 1920x1080 at browser zoom 100 %, 120 % and 200 %.
    for (final zoom in [1.0, 1.2, 2.0]) {
      final size = const Size(1920, 1080) / zoom;
      expect(await _compactAt(t, size), isFalse, reason: 'zoom $zoom');
    }
  });

  testWidgets('isCompact: Display size never turns the phone layout off', (
    t,
  ) async {
    // The phone default is 90 %: 411x914 then lays out as 457x1016 dp.
    for (final zoom in [0.5, 0.9, 1.0, 1.5]) {
      expect(
        await _compactScaled(t, const Size(411, 914), zoom),
        isTrue,
        reason: 'phone at ${zoom * 100} %',
      );
    }
    for (final zoom in [0.5, 1.0, 1.2, 2.0]) {
      expect(
        await _compactScaled(t, const Size(1920, 1080), zoom),
        isFalse,
        reason: 'desktop at ${zoom * 100} %',
      );
    }
  });

  testWidgets('Home: phone layout below 600 dp, desktop from 600', (t) async {
    final db = fixtureDb();
    final services = await fixtureServices(db, FakeStream());
    for (final (size, phone) in [
      (const Size(411, 914), true),
      (const Size(600, 914), false),
      (const Size(960, 540), false),
    ]) {
      await pumpScreen(
        t,
        HomeScreen(services: services, onSignedOut: () {}),
        size: size,
      );
      expect(
        find.byType(HomeFit),
        phone ? findsOneWidget : findsNothing,
        reason: '$size',
      );
    }
  });

  testWidgets('Home: the paged "+" tile is announced where it is painted', (
    t,
  ) async {
    final semantics = t.ensureSemantics();
    final db = fixtureDb();
    for (var i = 0; i < 24; i++) {
      db.root = setAt(db.root, 'tutor/v1/subjects/extra$i/meta', {
        'title': 'Extra $i',
        'goal': 'g',
        'status': 'failed',
        'created': 1,
        'rev': 1,
        'origin': 'generated',
      });
    }
    final services = await fixtureServices(db, FakeStream());
    await pumpScreen(
      t,
      HomeScreen(services: services, onSignedOut: () {}),
      size: const Size(411, 914),
    );
    for (var i = 0; i < 5; i++) {
      await t.drag(find.byType(PageView), const Offset(-400, 0));
      await t.pumpAndSettle();
    }
    final tile = find.bySemanticsLabel('New subject');
    expect(tile.hitTestable(), findsOneWidget);
    final painted = t.getRect(tile);
    final node = t.getSemantics(tile);
    final announced = _globalRect(node);
    expect(
      (announced.center - painted.center).distance,
      lessThan(1),
      reason: 'semantics $announced vs painted $painted',
    );
    expect(announced.size.width, closeTo(painted.width, 1));
    expect(announced.size.height, closeTo(painted.height, 1));
    semantics.dispose();
  });
}
