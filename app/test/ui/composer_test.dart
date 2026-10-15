// The answer composer on the phone (one question at a time, chips, Hint, the
// keyboard-open layout) and on the desktop (all boxes, comment, Ctrl+Enter).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/session/answers.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/ui/session/composer.dart';
import 'package:tutor/ui/session/session_screen.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_compose.dart';
import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _base = 'tutor/v1/sessions/$fixtureLiveSid';
const _phoneSize = Size(412, 915);

/// Opens the live session with the 3-question message as the latest turn.
Future<(FakeRtdb, FakeStream)> _open(
  WidgetTester t, {
  required bool phone,
  Size? size,
  List<String>? draft,
  bool questions = true,
}) async {
  debugPhone = phone;
  final db = fixtureDb();
  final msg = fixtureComposeMsg(fixtureNow);
  if (!questions) {
    msg
      ..remove('questions')
      ..remove('choices');
  }
  db.root = setAt(db.root, '$_base/msgs/$fixtureComposeKey', msg);
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  if (draft != null) {
    await s.kv.set(
      answersDraftKey(fixtureLiveSid, fixtureComposeKey),
      jsonEncode(draft),
    );
  }
  await pumpScreen(
    t,
    SessionScreen(services: s, now: () => DateTime(2030)),
    size: size ?? (phone ? _phoneSize : const Size(1366, 900)),
    settle: false,
  );
  for (final path in ['tutor/v1/live', '$_base/meta', '$_base/msgs']) {
    stream.listens[path]?.add(RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pumpAndSettle();
  return (db, stream);
}

// The tutor text is rich text (markdown spans).
Finder _rich(String s) => find.textContaining(s, findRichText: true);

String _boxText(WidgetTester t) =>
    t.widget<TextField>(find.byType(TextField)).controller!.text;

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('phone: Back/Next/Send gives ONE combined message', (t) async {
    final (db, stream) = await _open(t, phone: true);
    expect(find.text('1/3'), findsOneWidget);
    expect(find.textContaining('Which stroke makes the power?'), findsWidgets);
    expect(find.text('Your own comment'), findsNothing);
    expect(find.text('Ctrl+Enter to send'), findsNothing);
    expect(find.text('Back'), findsNothing);
    expect(find.text('Send'), findsNothing);

    await t.tap(find.text('The power stroke')); // a chip fills the box ...
    await t.pump();
    expect(_boxText(t), 'The power stroke');
    await t.enterText(find.byType(TextField), 'The power stroke, edited');
    await t.tap(find.text('Next')); // ... which is edited before Next
    await t.pumpAndSettle();
    expect(find.text('2/3'), findsOneWidget);
    expect(_boxText(t), '');
    await t.enterText(find.byType(TextField), 'two');
    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(find.text('1/3'), findsOneWidget);
    expect(_boxText(t), 'The power stroke, edited');
    await t.tap(find.text('Next'));
    await t.pumpAndSettle();
    expect(_boxText(t), 'two');
    await t.tap(find.text('Next'));
    await t.pumpAndSettle();
    expect(find.text('3/3'), findsOneWidget);
    expect(find.text('Next'), findsNothing);
    expect(
      t
          .widget<FilledButton>(find.widgetWithText(FilledButton, 'Send'))
          .onPressed,
      isNotNull,
    );
    await t.enterText(find.byType(TextField), 'three');
    await t.tap(find.text('Send'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    expect(msg['kind'], 'message');
    final body = msg['body'] as Map;
    expect(body['device'], 'phone');
    expect(
      body['text'],
      'Q1: Which stroke makes the power?\nA: The power stroke, edited\n\n'
      'Q2: Why does the crankshaft turn twice per cycle?\nA: two\n\n'
      'Q3: What closes the valves again after they open?\nA: three',
    );
  });

  testWidgets('phone: Hint chip sends "Hint" at once', (t) async {
    final (db, stream) = await _open(t, phone: true);
    await t.tap(find.text('Hint'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    expect(msg['body'], {
      'session': fixtureLiveSid,
      'text': 'Hint',
      'device': 'phone',
    });
  });

  testWidgets('phone: a saved draft resumes on the first open question', (
    t,
  ) async {
    await _open(t, phone: true, draft: ['one', 'two', '']);
    expect(find.text('3/3'), findsOneWidget);
    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(_boxText(t), 'two');
  });

  testWidgets('phone: every question answered resumes on the last', (t) async {
    await _open(t, phone: true, draft: ['one', 'two', 'three']);
    expect(find.text('3/3'), findsOneWidget);
    expect(_boxText(t), 'three');
  });

  testWidgets('phone: a plain box has no Ctrl+Enter hint', (t) async {
    await _open(t, phone: true, questions: false);
    expect(find.textContaining('Your answer. Reason'), findsOneWidget);
    expect(find.text('Ctrl+Enter to send'), findsNothing);
    expect(find.text('Send'), findsOneWidget);
  });

  testWidgets('phone, keyboard open: no header, last line, 85% text', (
    t,
  ) async {
    await _open(t, phone: true);
    expect(find.textContaining('This card:'), findsOneWidget);
    expect(_rich('Good. Now three quick ones'), findsOneWidget);
    double scale() =>
        MediaQuery.of(t.element(find.byType(Composer))).textScaler.scale(1);
    expect(scale(), 1);

    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(find.textContaining('This card:'), findsNothing);
    expect(find.textContaining('Today:'), findsNothing);
    expect(_rich('Good. Now three quick ones'), findsNothing);
    expect(_rich('a guess is fine.'), findsOneWidget);
    expect(scale(), closeTo(0.85, 1e-9));
    // The question and its box are still there.
    expect(find.text('1/3'), findsOneWidget);

    await t.tap(find.byIcon(Icons.expand_more));
    await t.pumpAndSettle();
    expect(_rich('Good. Now three quick ones'), findsOneWidget);

    t.view.resetViewInsets();
    await t.pumpAndSettle();
    expect(find.textContaining('This card:'), findsOneWidget);
    expect(scale(), 1);
  });

  testWidgets('desktop: all boxes, comment, Ctrl+Enter, chips, device', (
    t,
  ) async {
    final (db, stream) = await _open(t, phone: false);
    expect(find.text('Your own comment'), findsOneWidget);
    expect(find.text('Ctrl+Enter to send'), findsOneWidget);
    expect(find.text('1/3'), findsNothing);
    expect(find.text('Hint'), findsNWidgets(3)); // above each answer box
    expect(find.text('The intake stroke'), findsOneWidget);
    // Keyboard rules are the phone's: the desktop header stays.
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    expect(find.textContaining('This card:'), findsOneWidget);

    await t.ensureVisible(find.text('The camshaft lobe'));
    await t.tap(find.text('The camshaft lobe'));
    await t.pump();
    final boxes = find.byType(TextField);
    expect(
      t.widget<TextField>(boxes.at(2)).controller!.text,
      'The camshaft lobe',
    );
    await t.enterText(boxes.at(3), 'thanks');
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.enter);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    final body = msg['body'] as Map;
    expect(body['device'], 'desktop');
    expect(
      body['text'],
      allOf(contains('Q3: What closes'), contains('A: The camshaft lobe')),
    );
    expect(body['text'], endsWith('Comment: thanks'));
  });

  test('lastLineOf: the last non-blank line', () {
    expect(lastLineOf('a\nb\n\n  \n'), 'b');
    expect(lastLineOf('only'), 'only');
    expect(lastLineOf(' \n'), '');
  });
}
