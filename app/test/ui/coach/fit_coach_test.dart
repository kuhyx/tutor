// build-mobile-app R7: Coach (picker, chat, statement, code, reveal,
// post-mortem, paste form) fits one Pixel 6a screen; with the keyboard up
// the field typed in and its action stay visible.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/ui/coach/coach_picker.dart';
import 'package:tutor/ui/coach/coach_postmortem.dart';

import '../../coach/coach_fixtures.dart';
import '../../support/fake_rtdb.dart';
import '../../support/fake_stream.dart';
import '../../support/fit.dart';
import '../../support/services.dart';
import '../../support/ui.dart';
import 'coach_support.dart';

Finder _key(String k) => find.byKey(ValueKey(k));

/// A long statement and reply, so the panes must page.
final Map<String, Object?> _longOpen = {
  ...openData,
  'statement_md': 'Find two numbers that add up to `target`. ' * 30,
  'reply_md': 'Restate it. ${'What breaks with duplicates? ' * 20}',
};

Future<void> _keyboard(WidgetTester t, double scale, Finder field) async {
  await t.tap(field.hitTestable().first);
  pixelView(t, scale: scale, keyboard: fitKeyboard);
  await t.pumpAndSettle();
}

void main() {
  final rig = CoachRig();

  fitTest('Coach picker', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    await pumpFit(
      t,
      CoachPickerScreen(services: services(db, stream)),
      settle: false,
    );
    await answer(t, db, stream, data: listData);
    expectFits(t, state: 'picker');
    await _keyboard(t, scale, find.byType(TextField));
    expectFits(t, state: 'picker + keyboard');
  });

  fitTest('Coach chat, statement, keyboard', (t, scale) async {
    await rig.open(t, first: _longOpen);
    pixelView(t, scale: scale);
    for (var i = 0; i < 4; i++) {
      await rig.say(t, 'turn $i');
      await rig.reply(t, turnData);
    }
    await t.pumpAndSettle();
    expectFits(t, state: 'chat');
    await t.tap(find.text('Two Sum').hitTestable().last);
    await t.pumpAndSettle();
    expectFits(t, state: 'statement open');
    await _keyboard(t, scale, _key('answer'));
    expectFits(t, state: 'chat + keyboard');
    expectReachable(t, _key('send'), state: 'keyboard');
    expectReachable(t, _key('reveal'), state: 'keyboard');
  });

  fitTest('Coach code tab', (t, scale) async {
    await rig.open(t);
    pixelView(t, scale: scale);
    await t.tap(find.byIcon(Icons.code));
    await t.pumpAndSettle();
    expectFits(t, state: 'code');
    await rig.tap(t, 'run');
    await rig.reply(t, runData);
    await t.pumpAndSettle();
    expectFits(t, state: 'run result');
    await _keyboard(t, scale, _key('sql-editor'));
    expectFits(t, state: 'code + keyboard');
    expectReachable(t, _key('run'), state: 'keyboard');
  });

  fitTest('Coach reveal dialog', (t, scale) async {
    await rig.open(t);
    pixelView(t, scale: scale);
    await t.pumpAndSettle();
    await t.tap(_key('reveal'));
    await t.pumpAndSettle();
    await _keyboard(t, scale, find.byType(TextField).last);
    expectFits(t, state: 'reveal + keyboard');
    expectReachable(t, _key('reveal-ok'), state: 'keyboard');
  });

  fitTest('Coach paste form', (t, scale) async {
    await rig.open(t, first: null);
    await rig.reply(
      t,
      const {},
      code: 'bad_request',
      extra: {'reason': 'paste_statement'},
    );
    pixelView(t, scale: scale);
    await t.pumpAndSettle();
    expectFits(t, state: 'paste');
    await _keyboard(t, scale, _key('paste-statement'));
    expectFits(t, state: 'paste + keyboard');
    expectReachable(t, _key('paste-go'), state: 'keyboard');
  });

  fitTest('Coach post-mortem', (t, scale) async {
    pixelView(t, scale: scale);
    final db = FakeRtdb();
    final stream = FakeStream();
    await pumpFit(
      t,
      CoachPostMortemScreen(
        services: services(db, stream),
        lcId: lcId,
        summaryMd: '| step | rung |\n| --- | --- |\n| 1 | H0 |\n' * 3,
      ),
      settle: false,
    );
    await answer(t, db, stream, data: cardsData, settle: false);
    await t.pumpAndSettle();
    expectFits(t, state: 'cards');
  });
}
