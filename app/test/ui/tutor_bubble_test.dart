// The tutor bubble (kuhy, 2026-11-22): no academic hat; the text starts top
// left; the flag, the thinking head (with its research count, no chevron,
// no rule) and, on a low-effort reply only, the sad face sit in a column
// at the top right. The head opens the thinking under the message text.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/message.dart';
import 'package:tutor/ui/session/message_tile.dart';

import '../support/label_finders.dart';

const _thought = 'The learner knows coils; ask about the contact.';
const _text = 'What does the contact do?';

Message _msg({bool lowEffort = false}) => Message.fromJson({
  'role': 'tutor',
  'text': _text,
  'low_effort': lowEffort,
  'trace': [
    {'kind': 'thinking', 'text': _thought},
    {'kind': 'tool', 'name': 'WebSearch', 'input': 'relay contact NO NC'},
  ],
});

Future<void> _pump(WidgetTester t, Message m) => t.pumpWidget(
  MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: MessageTile(message: m, onReport: () {}),
      ),
    ),
  ),
);

const _head = 'Thinking · 1 research step';

void main() {
  testWidgets('flag and head top right, text top left, no hat', (t) async {
    await _pump(t, _msg());
    expect(find.byIcon(Icons.school_outlined), findsNothing);
    expect(find.byIcon(Icons.expand_more), findsNothing);
    expect(find.byIcon(Icons.expand_less), findsNothing);
    expect(find.byIcon(Icons.sentiment_dissatisfied_outlined), findsNothing);
    final text = t.getRect(find.textContaining(_text, findRichText: true));
    final flag = t.getRect(controlByLabel('⚑ Report'));
    final head = t.getRect(controlByLabel(_head));
    // The text's first line is level with the glyphs, left of them.
    expect(text.top, lessThan(flag.bottom));
    expect(text.right, lessThanOrEqualTo(flag.left));
    expect(head.left, greaterThanOrEqualTo(flag.right - 1), reason: 'beside');
    expect(head.center.dy, closeTo(flag.center.dy, 2));
    // No left rule around the head.
    final ruled = find.ancestor(
      of: controlByLabel(_head),
      matching: find.byWidgetPredicate(
        (w) =>
            w is Container &&
            w.decoration is BoxDecoration &&
            (w.decoration! as BoxDecoration).border is Border &&
            ((w.decoration! as BoxDecoration).border! as Border).left.width > 1,
      ),
    );
    expect(ruled, findsNothing);
  });

  testWidgets('the head opens the thinking under the text', (t) async {
    await _pump(t, _msg());
    expect(find.text(_thought), findsNothing);
    await t.tap(controlByLabel(_head));
    await t.pump();
    final thought = t.getRect(find.text(_thought));
    final text = t.getRect(find.textContaining(_text, findRichText: true));
    expect(thought.top, greaterThanOrEqualTo(text.bottom));
    expect(thought.left, closeTo(text.left, 1));
    expect(find.text('relay contact NO NC'), findsOneWidget);
    await t.tap(controlByLabel(_head));
    await t.pump();
    expect(find.text(_thought), findsNothing);
  });

  testWidgets('a low-effort reply adds the sad face beside them', (t) async {
    await _pump(t, _msg(lowEffort: true));
    final face = t.getRect(find.byIcon(Icons.sentiment_dissatisfied_outlined));
    final head = t.getRect(controlByLabel(_head));
    expect(face.left, greaterThanOrEqualTo(head.right - 1));
    expect(face.center.dy, closeTo(head.center.dy, 4));
  });
}
