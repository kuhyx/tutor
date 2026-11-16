// Typing on the phone (kuhy, 2026-11-16): with the keyboard up only the
// question and a tall answer box remain; a question with choices shows them
// first and keeps the field behind a keyboard glyph; "I don't know" sits
// beside Hint. Pixel 6a geometry, keyboard at its real height (~866 px).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/session/collapsed_tile.dart';
import 'package:tutor/ui/session/composer_parts.dart';
import 'package:tutor/ui/session/last_message.dart';
import 'package:tutor/ui/session/media.dart';
import 'package:tutor/ui/session/message_tile.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/composer.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/ui.dart';

const _long =
    'Imagine a future designer who sets out to make a better chair than '
    'yours: which single decision about the seat, the legs or the material '
    'would you tell them to change first, and what makes that decision '
    'matter more than the others you could have picked?';

Finder get _field => find.byType(TextField);

Finder get _hourglass => find.byIcon(Icons.hourglass_disabled);

Future<void> _keyboardUp(WidgetTester t) async {
  pixelView(t, keyboard: fitKeyboard);
  await t.pumpAndSettle();
}

// Dense phone text: a line is ~18 dp, the box adds ~24 dp of padding.
const double _twoLines = 2 * 18 + 24.0;
const double _fourLines = 4 * 18 + 24.0;
const double _capLines = 7 * 18 + 24.0;

Finder _asked(String part) => find.descendant(
  of: find.byType(QuestionLabel),
  matching: find.textContaining(part),
);

void _withPicture(Map<String, Object?> m) => m['images'] = [
  {
    'url':
        'https://upload.wikimedia.org/wikipedia/commons/d/dc/'
        '4StrokeEngine_Ortho_3D_Small.gif',
    'title': 'Four-stroke engine',
    'author': 'Zephyris',
    'licence': 'CC BY-SA 3.0',
    'page_url': 'https://commons.wikimedia.org/wiki/File:4Stroke.gif',
  },
];

void _longMessage(Map<String, Object?> m) {
  _withPicture(m);
  m['text'] = [
    for (var i = 0; i < 30; i++) 'Paragraph $i about the cycle of the engine.',
  ].join('\n\n');
}

void _longQuestion(Map<String, Object?> m) => m['questions'] = [
  _long,
  'Why does the crankshaft turn twice per cycle?',
  'What closes the valves again after they open?',
];

void main() {
  tearDown(() => debugPhone = null);

  testWidgets('keyboard up: no chips, no marks; a small box under the ask', (
    t,
  ) async {
    await openComposer(t, phone: true, edit: _longQuestion);
    pixelView(t);
    await t.pumpAndSettle();
    // The clock's stalled mark is in the header with the keyboard down.
    expect(_hourglass, findsOneWidget);
    await _keyboardUp(t);

    expect(_hourglass, findsNothing, reason: 'header marks cost a row');
    expect(find.text('The power stroke'), findsNothing, reason: 'no chips');
    expect(find.byKey(const ValueKey('fit-next')), findsNothing);
    final q = _asked('Imagine a future designer');
    expectReachable(t, q, state: 'long question');
    expectReachable(t, _field, state: 'answer box');
    final box = t.getRect(_field);
    expect(box.height, lessThanOrEqualTo(_fourLines), reason: 'about 3 lines');
    expect(box.height, greaterThan(_twoLines), reason: 'not a one-liner');
    expect(box.top - t.getRect(q).bottom, lessThan(32), reason: 'under it');
    for (final glyph in ['Hint', "I don't know", 'Next']) {
      final r = t.getRect(glyphsLabelled(glyph).hitTestable().first);
      expect(r.top, greaterThanOrEqualTo(box.top - 20), reason: glyph);
      expect(r.bottom, lessThanOrEqualTo(box.bottom + 20), reason: glyph);
    }
  });

  testWidgets('the box grows with the typing, up to a cap', (t) async {
    await openComposer(t, phone: true);
    await _keyboardUp(t);
    final empty = t.getRect(_field).height;
    await t.enterText(_field, 'one\ntwo\nthree\nfour\nfive');
    await t.pump();
    final five = t.getRect(_field).height;
    expect(five, greaterThan(empty), reason: 'grows');
    await t.enterText(_field, List.filled(30, 'a line').join('\n'));
    await t.pump();
    final many = t.getRect(_field);
    expect(many.height, lessThanOrEqualTo(_capLines), reason: 'capped');
    expect(many.bottom, lessThanOrEqualTo(fitFloor(t)));
    expectReachable(t, glyphsLabelled('Next'), state: 'long answer');
  });

  testWidgets('keyboard up: the last tutor message, picture and text, above', (
    t,
  ) async {
    await openComposer(t, phone: true, edit: _withPicture);
    await _keyboardUp(t);
    final q = _asked('Which stroke makes the power?');
    final text = rich('Good. Now three quick ones');
    final fig = find.byType(CommonsFigure);
    expectReachable(t, text, state: 'message text');
    expectReachable(t, fig, state: 'message picture');
    expectReachable(t, q, state: 'question');
    expect(t.getRect(text).bottom, lessThanOrEqualTo(t.getRect(q).top + 0.5));
    expect(t.getRect(fig).bottom, lessThanOrEqualTo(t.getRect(q).top + 0.5));
    expect(find.byType(CollapsedTile), findsNothing);
    expect(
      find.descendant(
        of: find.byType(MessageTile),
        matching: find.byType(QuestionLabel),
      ),
      findsNothing,
      reason: 'the ask is below, not repeated',
    );
    expectReachable(t, _field, state: 'answer box');
  });

  testWidgets('a long last message scrolls in its own region', (t) async {
    await openComposer(t, phone: true, edit: _longMessage);
    await _keyboardUp(t);
    await t.enterText(_field, 'typing');
    await t.pump();
    final region = find.descendant(
      of: find.byType(LastMessage),
      matching: find.byType(Scrollable),
    );
    final s = t.state<ScrollableState>(region.first);
    expect(s.position.maxScrollExtent, greaterThan(0), reason: 'scrolls');
    expectReachable(t, _asked('Which stroke makes the power?'));
    expectReachable(t, _field, state: 'answer box');
    expectReachable(t, glyphsLabelled('Next'), state: 'send');
    expect(
      t.getRect(find.byType(LastMessage)).bottom,
      lessThanOrEqualTo(t.getRect(_field).top),
    );
  });

  testWidgets('choices first: no field, chips, glyphs; typing opens it', (
    t,
  ) async {
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    expect(_field, findsNothing);
    expect(find.text('The power stroke'), findsOneWidget);
    expect(glyphsLabelled('Hint'), findsOneWidget);
    expect(glyphsLabelled("I don't know"), findsOneWidget);
    expect(glyphsLabelled('Type'), findsOneWidget);
    expect(glyphsLabelled('Next'), findsOneWidget);
    expectReachable(t, glyphsLabelled('Type'), state: 'collapsed');

    await t.tap(find.text('The power stroke'));
    await t.pump();
    expect(_field, findsNothing, reason: 'a pick keeps the field closed');
    await t.tap(glyphsLabelled('Type'));
    await t.pumpAndSettle();
    expect(boxText(t), 'The power stroke');
    expect(glyphsLabelled('Type'), findsNothing);
    expect(t.widget<TextField>(_field).focusNode?.hasFocus ?? true, isTrue);
  });

  testWidgets('a picked choice goes out without the field ever opening', (
    t,
  ) async {
    await openComposer(t, phone: true);
    pixelView(t);
    await t.pumpAndSettle();
    await t.tap(find.text('The power stroke'));
    await t.tap(glyphsLabelled('Next'));
    await t.pumpAndSettle();
    expect(bySpoken('2/3'), findsOneWidget);
    expect(_field, findsNothing);
  });

  testWidgets('no choices: the field is open, no keyboard glyph', (t) async {
    await openComposer(
      t,
      phone: true,
      edit: (m) => m['choices'] = [<String>[], <String>[], <String>[]],
    );
    pixelView(t);
    await t.pumpAndSettle();
    expect(_field, findsOneWidget);
    expect(glyphsLabelled('Type'), findsNothing);
    expect(glyphsLabelled("I don't know"), findsOneWidget);
  });

  testWidgets('a draft of own words opens only its own question field', (
    t,
  ) async {
    await openComposer(t, phone: true, draft: ['', 'my own words', '']);
    pixelView(t);
    await t.pumpAndSettle();
    expect(bySpoken('1/3'), findsOneWidget);
    expect(_field, findsNothing, reason: 'question 1 has no words yet');
    await t.tap(glyphsLabelled('Next'));
    await t.pumpAndSettle();
    expect(boxText(t), 'my own words');
    expect(glyphsLabelled('Type'), findsNothing);
    await t.tap(glyphsLabelled('Next'));
    await t.pumpAndSettle();
    expect(_field, findsNothing, reason: 'question 3 stays closed');
  });

  testWidgets("I don't know sends a fixed message at once", (t) async {
    final (db, stream) = await openComposer(t, phone: true);
    await t.tap(controlByLabel("I don't know"));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0006'});
    expect(msg['body'], {
      'session': fixtureLiveSid,
      'text': "I don't know",
      'device': 'phone',
    });
  });

  testWidgets('desktop: boxes beside chips, no phone glyphs', (t) async {
    await openComposer(t, phone: false);
    expect(_field, findsNWidgets(3));
    expect(find.text('The intake stroke'), findsOneWidget);
    expect(glyphsLabelled("I don't know"), findsNothing);
    expect(glyphsLabelled('Type'), findsNothing);
  });
}
