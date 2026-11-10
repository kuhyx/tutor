// Phone session with the keyboard up reclaims the screen (todo 340c295b-10):
// no top bar, no sidebar, no message feed, no pencil, one row
// [hint][field][action], 13 sp / 20 dp / 40 dp density, the status bar
// hidden via SystemChrome; keyboard down brings the bar and sidebar back.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/ui/session/composer_parts.dart';
import 'package:tutor/util/device.dart';

import '../support/composer.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _keyboard = 300.0;

Finder get _question =>
    find.textContaining('Which stroke makes the power?').hitTestable();

Finder get _field => find.byType(TextField).hitTestable();

ScaffoldState _scaffold(WidgetTester t) =>
    t.state<ScaffoldState>(find.byType(Scaffold).first);

Future<void> _keyboardUp(WidgetTester t) async {
  pixelView(t, keyboard: _keyboard);
  await t.pumpAndSettle();
}

Future<void> _keyboardDown(WidgetTester t) async {
  pixelView(t);
  await t.pumpAndSettle();
}

/// SystemChrome system-UI calls, in order (fake platform channel).
List<MethodCall> _recordChrome(WidgetTester t) {
  final calls = <MethodCall>[];
  t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
    SystemChannels.platform,
    (call) async {
      if (call.method.startsWith('SystemChrome.setEnabledSystemUI')) {
        calls.add(call);
      }
      return null;
    },
  );
  addTearDown(
    () => t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      null,
    ),
  );
  return calls;
}

/// [part] inside the composer's question label (the feed repeats it).
Finder _asked(String part) => find.descendant(
  of: find.byType(QuestionLabel),
  matching: find.textContaining(part),
);

void main() {
  tearDown(() => debugPhone = null);

  testWidgets('keyboard up: bar, sidebar, feed and pencil gone; one row', (
    t,
  ) async {
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    await t.tap(_field.first);
    await _keyboardUp(t);

    expect(find.byType(AppBar), findsNothing);
    expect(glyphsLabelled('Card and progress'), findsNothing);
    expect(find.byIcon(Icons.expand_more), findsNothing);
    expect(find.byIcon(Icons.edit_outlined), findsNothing);
    expect(find.byType(CollapsedTile), findsNothing);
    expect(rich('Good. Now three quick ones'), findsNothing);
    expectReachable(t, _question, state: 'keyboard');
    expectReachable(t, _field, state: 'keyboard');
    expectReachable(t, glyphsLabelled('Next'), state: 'keyboard');
    expectReachable(t, glyphsLabelled('Hint'), state: 'keyboard');
    for (final s in t.stateList<ScrollableState>(find.byType(Scrollable))) {
      if (s.position.axis != Axis.vertical) continue;
      expect(s.position.maxScrollExtent, 0, reason: '${s.context.widget}');
    }
    // Hint, field and action share one row.
    final field = t.getRect(_field.first);
    for (final glyph in ['Hint', 'Next']) {
      final r = t.getRect(glyphsLabelled(glyph).hitTestable().first);
      expect(r.center.dy, closeTo(field.center.dy, 12), reason: glyph);
    }
    expect(
      t.getRect(glyphsLabelled('Hint').first).right,
      lessThanOrEqualTo(field.left + 0.5),
    );
    expect(
      t.getRect(glyphsLabelled('Next').first).left,
      greaterThanOrEqualTo(field.right - 0.5),
    );
    // Choice chips sit above the row.
    expect(
      t.getRect(find.text('The power stroke')).bottom,
      lessThanOrEqualTo(field.top + 0.5),
    );

    // No edge swipe opens the drawer.
    final size = t.view.physicalSize / t.view.devicePixelRatio;
    await t.dragFrom(Offset(size.width - 2, 300), const Offset(-300, 0));
    await t.pumpAndSettle();
    expect(_scaffold(t).isEndDrawerOpen, isFalse);
  });

  testWidgets('keyboard down: bar and sidebar back, tile has no chevron', (
    t,
  ) async {
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    await t.tap(_field.first);
    await _keyboardUp(t);
    await _keyboardDown(t);
    expect(find.byType(AppBar), findsOneWidget);
    // The row stays above the gesture bar.
    expectReachable(t, _field, state: 'keyboard down');
    expectReachable(t, glyphsLabelled('Next'), state: 'keyboard down');
    expect(find.byIcon(Icons.expand_more), findsNothing);
    expect(find.byIcon(Icons.edit_outlined), findsNothing);
    await t.tap(glyphsLabelled('Card and progress'));
    await t.pumpAndSettle();
    expect(_scaffold(t).isEndDrawerOpen, isTrue);
  });

  testWidgets('an open sidebar closes when the keyboard rises', (t) async {
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    _scaffold(t).openEndDrawer();
    await t.pumpAndSettle();
    expect(_scaffold(t).isEndDrawerOpen, isTrue);
    await _keyboardUp(t);
    expect(_scaffold(t).isEndDrawerOpen, isFalse);
  });

  testWidgets('plain box, keyboard up: the folded tile has no chevron and '
      'a tap opens it', (t) async {
    await openComposer(t, phone: true, questions: false);
    pixelView(t);
    await t.pumpAndSettle();
    await t.tap(_field.first);
    await _keyboardUp(t);
    expect(find.byType(AppBar), findsNothing);
    expect(find.byType(CollapsedTile), findsOneWidget);
    expect(find.byIcon(Icons.expand_more), findsNothing);
    expect(find.byIcon(Icons.edit_outlined), findsNothing);
    await t.tap(find.byType(CollapsedTile));
    await t.pumpAndSettle();
    expect(rich('Good. Now three quick ones'), findsOneWidget);
  });

  testWidgets('density: 13 sp text, 20 dp icons, 40 dp targets', (t) async {
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    final field = t.widget<TextField>(find.byType(TextField));
    expect(field.style?.fontSize, 13);
    final q = t.widget<Text>(_asked('Which stroke makes the power?'));
    expect(q.style?.fontSize, 13);
    for (final glyph in ['Hint', 'Next']) {
      final b = glyphsLabelled(glyph);
      final icon = t.widget<Icon>(
        find.descendant(of: b, matching: find.byType(Icon)).first,
      );
      expect(icon.size, 20, reason: glyph);
      final button = find.descendant(of: b, matching: find.byType(IconButton));
      expect(t.getSize(button), const Size(40, 40), reason: glyph);
    }
  });

  testWidgets('3 questions: check, check, send; dots; swipe right = back', (
    t,
  ) async {
    final (db, stream) = await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    expect(find.text('1/3'), findsNothing);
    final dots = find.byKey(const ValueKey('step-dots'));
    expect(dots, findsOneWidget);
    expect(glyphsLabelled('Back'), findsNothing);
    expect(find.byIcon(Icons.check), findsOneWidget);

    await t.enterText(find.byType(TextField), 'one');
    await t.tap(glyphsLabelled('Next'));
    await t.pumpAndSettle();
    expect(_asked('Why does the crankshaft'), findsOneWidget);
    // Swipe right on the question: back to the first, answer kept.
    await t.drag(_asked('Why does the crankshaft'), const Offset(300, 0));
    await t.pumpAndSettle();
    expect(_asked('Which stroke makes the power?'), findsOne);
    expect(boxText(t), 'one');
    await t.tap(glyphsLabelled('Next'));
    await t.pumpAndSettle();
    // Question 2 left empty: it goes out as skipped.
    await t.tap(glyphsLabelled('Next'));
    await t.pumpAndSettle();
    expect(glyphsLabelled('Next'), findsNothing);
    expect(find.byIcon(Icons.send), findsOneWidget);
    await t.enterText(find.byType(TextField), 'three');
    await t.pump();
    await t.tap(glyphsLabelled('Send'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    expect(
      (msg['body'] as Map)['text'],
      'Q1: Which stroke makes the power?\nA: one\n\n'
      'Q2: Why does the crankshaft turn twice per cycle?\nA: (skipped)\n\n'
      'Q3: What closes the valves again after they open?\nA: three',
    );
  });

  testWidgets('status bar hides with the keyboard, back on close and leave', (
    t,
  ) async {
    final calls = _recordChrome(t);
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    expect(calls, isEmpty);
    await t.tap(_field.first);
    await _keyboardUp(t);
    expect(calls, hasLength(1));
    expect(calls.last.method, 'SystemChrome.setEnabledSystemUIOverlays');
    expect(calls.last.arguments, ['SystemUiOverlay.bottom']);
    await _keyboardDown(t);
    expect(calls, hasLength(2));
    expect(calls.last.method, 'SystemChrome.setEnabledSystemUIMode');
    expect(calls.last.arguments, 'SystemUiMode.edgeToEdge');
    // Up again, then leave the screen: restored.
    await t.tap(_field.first);
    await _keyboardUp(t);
    expect(calls, hasLength(3));
    await t.pumpWidget(const SizedBox());
    expect(calls, hasLength(4));
    expect(calls.last.arguments, 'SystemUiMode.edgeToEdge');
  });

  testWidgets('desktop: keyboard insets change nothing', (t) async {
    final calls = _recordChrome(t);
    await openComposer(t, phone: false);
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(find.byType(AppBar), findsOneWidget);
    expect(find.byIcon(Icons.edit_outlined), findsNWidgets(3));
    expect(calls, isEmpty);
  });
}
