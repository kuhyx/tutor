// A LeetCode theory lesson (kuhy, 2026-11-22): the top bar shows the unit
// (a pencil and its name), then the LeetCode accounting as glyph + number,
// in place of every tutor number, on desktop and on the phone.
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_header.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/util/device.dart';
import 'package:tutor/widgets/content_text.dart';

import '../../tool/fixture/fixture_leetcode.dart';
import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _base = 'tutor/v1-e2e/sessions/$fixtureLiveSid';

Future<void> _feed(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  for (final path in ['tutor/v1-e2e/live', '$_base/meta', '$_base/msgs']) {
    stream.emit(path, RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pumpAndSettle();
}

Future<void> _open(
  WidgetTester t,
  Size size, {
  String? mode = 'normal',
  bool stopped = false,
}) async {
  final db = fixtureDb();
  if (mode != null) {
    db.root = fixtureWithLeetcode(db.root, fixtureLeetcode(mode));
  }
  if (stopped) {
    db.root = setAt(db.root, '$_base/meta/stopped', true);
  }
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    SessionScreen(services: s, now: () => DateTime(2030)),
    size: size,
    settle: false,
  );
  await _feed(t, db, stream);
}

Future<void> _openPhone(WidgetTester t, {String? mode = 'normal'}) async {
  debugPhone = true;
  addTearDown(() => debugPhone = false);
  pixelView(t);
  final db = fixtureDb();
  if (mode != null) {
    db.root = fixtureWithLeetcode(db.root, fixtureLeetcode(mode));
  }
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpFit(
    t,
    SessionScreen(services: s, now: () => DateTime(2030)),
    settle: false,
  );
  await _feed(t, db, stream);
}

Finder _inBar(Finder f) =>
    find.descendant(of: find.byType(AppBar), matching: f);

Finder get _timer => _inBar(find.byIcon(Icons.timer_outlined));
Finder get _credit => _inBar(find.byIcon(Icons.diamond_outlined));
Finder get _owed => _inBar(find.byIcon(Icons.circle_outlined));
Finder get _cards => _inBar(find.byIcon(Icons.style_outlined));

void _theBarHoldsTheAccounting(WidgetTester t, {String ratio = '7/12'}) {
  expect(_inBar(find.byIcon(Icons.edit_outlined)), findsOneWidget);
  expect(
    find.descendant(
      of: find.byType(AppBar),
      matching: find.widgetWithText(ContentText, 'prefix-sums'),
    ),
    findsOneWidget,
  );
  expect(_inBar(find.text(ratio)), findsOneWidget);
  expect(_timer, findsOneWidget);
  expect(_credit, findsOneWidget);
  expect(_owed, findsOneWidget);
  expect(_cards, findsOneWidget);
  expect(find.byType(SessionHeader), findsOneWidget, reason: 'no second row');
  // Every tutor number is gone: bolt quota, bank, prepaid, this card.
  for (final gone in [
    Icons.bolt,
    Icons.savings_outlined,
    Icons.event_available,
  ]) {
    expect(find.byIcon(gone), findsNothing);
  }
  expect(find.text('How a car works'), findsNothing);
}

void main() {
  testWidgets('wide: unit, then ⏱ ◆ ○ ▤ in the bar, tutor numbers gone', (
    t,
  ) async {
    await _open(t, const Size(1920, 1080));
    _theBarHoldsTheAccounting(t);
    expect(_inBar(find.text('1')), findsOneWidget);
    expect(_inBar(find.text('6')), findsOneWidget);
    expect(_inBar(find.text('3/9')), findsOneWidget);
    // Left to right: the mock-up's order.
    final xs = [
      for (final f in [_timer, _credit, _owed, _cards]) t.getRect(f).left,
    ];
    expect(xs, [...xs]..sort());
    // The marks stay: this fixture's reply is long overdue.
    expect(_inBar(find.byIcon(Icons.hourglass_disabled)), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('spoken labels carry the numbers; one word names a glyph', (
    t,
  ) async {
    await _open(t, const Size(1920, 1080));
    expect(
      bySpoken('LeetCode: 7 of 12 min to the next credit'),
      findsOneWidget,
    );
    expect(bySpoken('LeetCode credits today: 1'), findsOneWidget);
    expect(bySpoken('LeetCode solves still owed today: 6'), findsOneWidget);
    expect(bySpoken('Cards taught in this unit: 3 of 9'), findsOneWidget);
    expect(bySpoken('Unit: prefix-sums'), findsOneWidget);
    for (final tip in t.widgetList<Tooltip>(find.byType(Tooltip))) {
      expect(tip.message, isNot(contains(' ')));
    }
  });

  testWidgets('unknown counts paint ?, never 0', (t) async {
    await _open(t, const Size(1920, 1080), mode: 'unknown');
    expect(_inBar(find.text('?')), findsNWidgets(3));
    expect(_inBar(find.text('0')), findsNothing);
    expect(_inBar(find.text('3/9')), findsOneWidget);
    expect(bySpoken('LeetCode credits today: unknown'), findsOneWidget);
  });

  testWidgets('full: a timer-off mark in the warning colour, no numbers', (
    t,
  ) async {
    await _open(t, const Size(1920, 1080), mode: 'full');
    expect(_inBar(find.byIcon(Icons.timer_outlined)), findsNothing);
    final off = _inBar(find.byIcon(Icons.timer_off_outlined));
    expect(off, findsOneWidget);
    expect(t.widget<Icon>(off).color, AppPalette.warning);
    expect(_inBar(find.text('12/12')), findsNothing);
    expect(_inBar(find.text('2')), findsOneWidget);
  });

  testWidgets("a session without the map keeps today's bar", (t) async {
    await _open(t, const Size(1920, 1080), mode: null);
    expect(_inBar(find.byIcon(Icons.bolt)), findsWidgets);
    expect(_inBar(find.byIcon(Icons.edit_outlined)), findsNothing);
    expect(_inBar(find.byIcon(Icons.diamond_outlined)), findsNothing);
    expect(find.text('How a car works'), findsOneWidget);
  });

  testWidgets('a stopped session with a leftover map keeps the ordinary bar', (
    t,
  ) async {
    await _open(t, const Size(1920, 1080), stopped: true);
    expect(_inBar(find.byIcon(Icons.edit_outlined)), findsNothing);
    expect(_inBar(find.byIcon(Icons.diamond_outlined)), findsNothing);
    expect(find.text('prefix-sums'), findsNothing);
    expect(find.text('How a car works'), findsOneWidget);
  });

  for (final w in [1366.0, 900.0]) {
    testWidgets('$w px: the stats take the second line, all on the bar', (
      t,
    ) async {
      await _open(t, Size(w, 900));
      _theBarHoldsTheAccounting(t);
      final title = t.getRect(_inBar(find.byType(ContentText)).first);
      final stats = t.getRect(_inBar(find.byType(SessionHeader)));
      expect(stats.top, greaterThanOrEqualTo(title.bottom - 1));
      expect(stats.right, lessThanOrEqualTo(w));
      expect(t.takeException(), isNull);
    });
  }

  testWidgets('phone: ⏱ ○ ◆ ▤ in a row under the title, below the status bar', (
    t,
  ) async {
    await _openPhone(t);
    _theBarHoldsTheAccounting(t);
    const top = fitTopPx / fitDpr;
    final bar = t.getRect(find.byType(AppBar));
    for (final f in [_timer, _credit, _owed, _cards]) {
      final r = t.getRect(f);
      expect(r.top, greaterThanOrEqualTo(top), reason: 'under the status bar');
      expect(r.bottom, lessThanOrEqualTo(bar.bottom + 1));
      expect(r.right, lessThanOrEqualTo(fitScreen.width / fitDpr));
    }
    expect(t.takeException(), isNull);
  });

  testWidgets('phone, unknown counts: ? shows, no overflow', (t) async {
    await _openPhone(t, mode: 'unknown');
    expect(_inBar(find.text('?')), findsNWidgets(3));
    expect(t.takeException(), isNull);
  });

  testWidgets('phone, an ordinary session: no row, as before', (t) async {
    await _openPhone(t, mode: null);
    expect(_inBar(find.byIcon(Icons.bolt)), findsNothing);
    expect(find.byIcon(Icons.bolt), findsWidgets, reason: 'the row above chat');
    expect(_inBar(find.byIcon(Icons.diamond_outlined)), findsNothing);
  });
}
