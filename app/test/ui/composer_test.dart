// The answer composer on the phone (one question at a time, chips, Hint, the
// keyboard-open layout) and on the desktop (all boxes, Ctrl+Enter).
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/composer.dart';
import '../support/ui.dart';

void main() {
  tearDown(() => debugPhone = false);

  testWidgets('phone: Back/Next/Send gives ONE combined message', (t) async {
    final (db, stream) = await openComposer(t, phone: true);
    expect(find.text('1/3'), findsOneWidget);
    expect(find.textContaining('Which stroke makes the power?'), findsWidgets);
    expect(find.text('Your own comment'), findsNothing);
    expect(find.text('Ctrl+Enter to send'), findsNothing);
    expect(find.text('Back'), findsNothing);
    expect(find.text('Send'), findsNothing);

    await t.tap(find.text('The power stroke')); // a chip fills the box ...
    await t.pump();
    expect(boxText(t), 'The power stroke');
    await t.enterText(find.byType(TextField), 'The power stroke, edited');
    await t.tap(find.text('Next')); // ... which is edited before Next
    await t.pumpAndSettle();
    expect(find.text('2/3'), findsOneWidget);
    expect(boxText(t), '');
    await t.enterText(find.byType(TextField), 'two');
    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(find.text('1/3'), findsOneWidget);
    expect(boxText(t), 'The power stroke, edited');
    await t.tap(find.text('Next'));
    await t.pumpAndSettle();
    expect(boxText(t), 'two');
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
    final (db, stream) = await openComposer(t, phone: true);
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
    await openComposer(t, phone: true, draft: ['one', 'two', '']);
    expect(find.text('3/3'), findsOneWidget);
    await t.tap(find.text('Back'));
    await t.pumpAndSettle();
    expect(boxText(t), 'two');
  });

  testWidgets('phone: every question answered resumes on the last', (t) async {
    await openComposer(t, phone: true, draft: ['one', 'two', 'three']);
    expect(find.text('3/3'), findsOneWidget);
    expect(boxText(t), 'three');
  });

  testWidgets('phone: a plain box has no Ctrl+Enter hint', (t) async {
    await openComposer(t, phone: true, questions: false);
    expect(find.textContaining('Your answer. Reason'), findsOneWidget);
    expect(find.text('Ctrl+Enter to send'), findsNothing);
    expect(find.text('Send'), findsOneWidget);
  });

  testWidgets('phone: Next card says device=phone too', (t) async {
    final (db, stream) = await openComposer(t, phone: true);
    db.root = setAt(db.root, '$composeBase/meta/card_done', true);
    stream.listens['$composeBase/meta']!.add(
      RtdbPut('/', getAt(db.root, '$composeBase/meta')),
    );
    await t.pumpAndSettle();
    await t.tap(find.text('Next card'));
    await sent(t);
    final next = await answer(t, db, stream, settle: false);
    expect(next['kind'], 'next');
    expect(next['body'], {'session': fixtureLiveSid, 'device': 'phone'});
  });

  testWidgets('desktop: all boxes, Ctrl+Enter, chips, device', (t) async {
    final (db, stream) = await openComposer(t, phone: false);
    expect(find.text('Your own comment'), findsNothing);
    expect(find.byType(TextField), findsNWidgets(3)); // one per question
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
    await t.enterText(boxes.at(0), 'thanks');
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
    expect(body['text'], contains('A: thanks\n'));
    expect(body['text'], isNot(contains('Comment:')));
  });

  testWidgets('desktop: an old draft with a comment entry loads harmlessly', (
    t,
  ) async {
    final (db, stream) = await openComposer(
      t,
      phone: false,
      draft: ['one', 'two', 'three', 'old comment'],
    );
    final boxes = find.byType(TextField);
    expect(boxes, findsNWidgets(3));
    expect(t.widget<TextField>(boxes.at(2)).controller!.text, 'three');
    expect(find.text('old comment'), findsNothing);
    await t.ensureVisible(find.text('Send'));
    await t.tap(find.text('Send'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    final text = (msg['body'] as Map)['text'] as String;
    expect(text, endsWith('A: three'));
    expect(text, isNot(contains('old comment')));
  });

  test('lastLineOf: the last non-blank line', () {
    expect(lastLineOf('a\nb\n\n  \n'), 'b');
    expect(lastLineOf('only'), 'only');
    expect(lastLineOf(' \n'), '');
  });
}
