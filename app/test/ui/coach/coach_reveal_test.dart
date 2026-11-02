import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../coach/coach_fixtures.dart';
import 'coach_support.dart';

void main() {
  late CoachRig rig;
  setUp(() => rig = CoachRig());

  Future<void> typeReveal(WidgetTester t, String text) async {
    await t.enterText(find.byKey(const ValueKey('reveal-text')), text);
    await t.pump();
  }

  bool okEnabled(WidgetTester t) =>
      t.widget<IconButton>(find.byKey(const ValueKey('reveal-ok'))).onPressed !=
      null;

  testWidgets('the Reveal icon needs the word typed, nothing is sent first', (
    t,
  ) async {
    await rig.open(t);
    await rig.tap(t, 'reveal');
    expect(rig.kind(), 'lc_open');
    expect(okEnabled(t), isFalse);
    await typeReveal(t, 'reveal please');
    expect(okEnabled(t), isFalse);
    await typeReveal(t, ' reveal ');
    expect(okEnabled(t), isTrue);
    await rig.tap(t, 'reveal-ok');
    expect(rig.kind(), 'lc_turn');
    expect(rig.body()['text'], 'reveal');
    expect(rig.body()['intent'], 'chat');
  });

  testWidgets('cancelling sends nothing', (t) async {
    await rig.open(t);
    await rig.tap(t, 'reveal');
    await rig.tap(t, 'reveal-cancel');
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('reveal-text')), findsNothing);
    expect(rig.kind(), 'lc_open');
  });

  testWidgets('the bare word in the answer box asks first', (t) async {
    await rig.open(t);
    await rig.say(t, 'Reveal');
    expect(rig.kind(), 'lc_open');
    await typeReveal(t, 'reveal');
    await rig.tap(t, 'reveal-ok');
    expect(rig.body()['text'], 'reveal');
    expect(find.text('Reveal'), findsNothing);
  });

  testWidgets('any other sentence with the word is plain chat', (t) async {
    await rig.open(t);
    await rig.say(t, 'reveal please');
    expect(rig.kind(), 'lc_turn');
    expect(rig.body()['text'], 'reveal please');
    expect(find.byKey(const ValueKey('reveal-text')), findsNothing);
  });

  testWidgets('frustration choices send their exact text; reveal asks', (
    t,
  ) async {
    await rig.open(t);
    await rig.say(t, 'going in circles');
    await rig.reply(t, {
      'reply_md': 'Sorry. Pick one.',
      'choices': ['write it', 'hint!', 'reveal'],
    });
    await rig.tap(t, 'choice-hint!');
    expect(rig.body()['text'], 'hint!');
    expect(find.byKey(const ValueKey('choice-write it')), findsNothing);
    await rig.reply(t, {
      'reply_md': 'Try this.',
      'choices': ['reveal'],
    });
    await rig.tap(t, 'choice-reveal');
    expect(rig.body()['text'], 'hint!');
    await typeReveal(t, 'reveal');
    await rig.tap(t, 'reveal-ok');
    expect(rig.body()['text'], 'reveal');
    expect(lcId, isNotEmpty);
  });
}
