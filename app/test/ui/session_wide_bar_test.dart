// The wide Session screen (kuhy, 2026-11-22): the title, the day's stats
// and every action sit in the top bar; the sidebar is a 300 px strip with
// only the target card; Known opens as a dialog. Below about 1400 px the
// stats take a second line under the title, and the actions never wrap.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_header.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/widgets/content_text.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _base = 'tutor/v1-e2e/sessions/$fixtureLiveSid';

const _actions = [
  'Switch card',
  'Mark card done',
  'Stop here',
  'Edit cards',
  'History',
  'Report a problem',
  'Known',
  'Copy session id',
];

Future<void> _open(WidgetTester t, Size size) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    SessionScreen(services: s, now: () => DateTime(2030)),
    size: size,
    settle: false,
  );
  for (final path in ['tutor/v1-e2e/live', '$_base/meta', '$_base/msgs']) {
    stream.emit(path, RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pumpAndSettle();
}

Finder _inBar(Finder f) =>
    find.descendant(of: find.byType(AppBar), matching: f);

Rect _title(WidgetTester t) =>
    t.getRect(_inBar(find.byType(ContentText)).first);

void main() {
  testWidgets('wide: title, stats, then every action, in order', (t) async {
    await _open(t, const Size(1920, 1080));
    final stats = _inBar(find.byType(SessionHeader));
    expect(stats, findsOneWidget);
    expect(find.byType(SessionHeader), findsOneWidget, reason: 'no row');
    final title = _title(t);
    expect(t.getRect(stats).left, greaterThanOrEqualTo(title.right - 1));
    expect(t.getRect(stats).center.dy, closeTo(title.center.dy, 8));
    var left = t.getRect(stats).right;
    for (final a in _actions) {
      final r = t.getRect(_inBar(controlByLabel(a)).hitTestable());
      expect(r.left, greaterThanOrEqualTo(left - 1), reason: a);
      left = r.right;
    }
    // The side: a 300 px strip with only the target card.
    final target = bySpoken('Target card');
    expect(target, findsOneWidget);
    final pane = find.ancestor(
      of: target,
      matching: find.byWidgetPredicate((w) => w is SizedBox && w.width == 300),
    );
    expect(pane, findsOneWidget);
    for (final a in _actions) {
      expect(find.descendant(of: pane, matching: bySpoken(a)), findsNothing);
    }
    expect(
      find.descendant(of: pane, matching: find.byType(ContentText)),
      findsOneWidget,
      reason: 'the card front only',
    );
  });

  testWidgets('Known opens a dialog, newest first; Esc closes', (t) async {
    await _open(t, const Size(1920, 1080));
    await t.tap(_inBar(glyphsLabelled('Known')));
    await t.pumpAndSettle();
    final dialog = find.byType(Dialog);
    expect(dialog, findsOneWidget);
    final names = find.descendant(
      of: dialog,
      matching: find.byType(ContentText),
    );
    expect(names, findsWidgets);
    expect(find.descendant(of: dialog, matching: bySpoken('Known')), findsOne);
    await t.sendKeyEvent(LogicalKeyboardKey.escape);
    await t.pumpAndSettle();
    expect(find.byType(Dialog), findsNothing);
  });

  for (final w in [1366.0, 900.0]) {
    testWidgets('$w px: stats on a second line, every action on the bar', (
      t,
    ) async {
      await _open(t, Size(w, 900));
      final title = _title(t);
      final stats = t.getRect(_inBar(find.byType(SessionHeader)));
      expect(stats.top, greaterThanOrEqualTo(title.bottom - 1));
      for (final a in _actions) {
        final r = t.getRect(_inBar(controlByLabel(a)).hitTestable());
        expect(r.right, lessThanOrEqualTo(w), reason: a);
        expect(r.top, lessThan(title.bottom), reason: '$a on the title line');
      }
      expect(glyphsLabelled('Card and progress'), findsNothing);
    });
  }

  testWidgets('below 900 px: the drawer and stats row stay', (t) async {
    await _open(t, const Size(800, 900));
    expect(glyphsLabelled('Card and progress'), findsOneWidget);
    expect(_inBar(find.byType(SessionHeader)), findsNothing);
    expect(find.byType(SessionHeader), findsOneWidget);
  });
}
