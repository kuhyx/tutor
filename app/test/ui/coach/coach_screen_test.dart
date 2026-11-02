import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/coach/coach_drafts.dart';
import 'package:tutor/coach/coach_requests.dart';
import 'package:tutor/ui/coach/coach_postmortem.dart';

import '../../coach/coach_fixtures.dart';
import 'coach_support.dart';

void main() {
  final rig = CoachRig();

  testWidgets('opens: title, statement, the opener, gate chip', (t) async {
    await rig.open(t);
    expect(find.text('Two Sum'), findsWidgets);
    expect(find.textContaining('Find two numbers'), findsOneWidget);
    expect(find.textContaining('Restate it'), findsOneWidget);
    expect(find.byKey(const Key('gate')), findsOneWidget);
    expect(find.text('req: 0/3'), findsOneWidget);
  });

  testWidgets('while opening: the status; a damaged reply shows why', (
    t,
  ) async {
    await rig.open(t, first: null);
    expect(find.byType(LinearProgressIndicator), findsNothing);
    await rig.reply(t, {...openData, 'langs': 5});
    expect(find.textContaining('expected array'), findsOneWidget);
  });

  testWidgets('a message goes as lc_turn; the reply pins its code', (t) async {
    await rig.open(t);
    await rig.type(t, 'req: O(1) lookup');
    await rig.tap(t, 'send');
    expect(rig.kind(), 'lc_turn');
    expect(rig.body(), {
      'lc_id': lcId,
      'text': 'req: O(1) lookup',
      'intent': 'chat',
    });
    expect(find.text('req: O(1) lookup'), findsOneWidget);
    await rig.reply(t, turnData);
    expect(find.byKey(const ValueKey('pinned')), findsOneWidget);
    expect(find.textContaining('seen = {}'), findsNWidgets(2));
    expect(find.text('H1'), findsOneWidget);
    expect(find.text('3/16'), findsOneWidget);
    await rig.tap(t, 'unpin');
    expect(find.byKey(const ValueKey('pinned')), findsNothing);
  });

  testWidgets('the pin survives a reply with nothing to pin', (t) async {
    await rig.open(t);
    await rig.say(t, 'x');
    await rig.reply(t, turnData);
    await rig.say(t, 'y');
    await rig.reply(t, {'reply_md': 'Why?'});
    expect(find.byKey(const ValueKey('pinned')), findsOneWidget);
  });

  testWidgets('the pin stays above the answer box with the keyboard up', (
    t,
  ) async {
    await rig.open(t);
    pixel(t, keyboard: 300);
    await rig.say(t, 'x');
    await rig.reply(t, {
      'reply_md': List.generate(40, (i) => 'line $i').join('\n\n'),
    });
    await rig.say(t, 'y');
    await rig.reply(t, turnData);
    await t.drag(find.byType(ListView).first, const Offset(0, 600));
    await t.pump();
    final pin = t.getRect(find.byKey(const ValueKey('pinned')));
    final box = t.getRect(find.byKey(const ValueKey('answer')));
    expect(pin.bottom, lessThanOrEqualTo(box.top));
    expect(
      t.getTopLeft(find.byKey(const ValueKey('pinned'))).dy,
      greaterThan(0),
    );
    expect(find.byKey(const ValueKey('pinned')).hitTestable(), findsOneWidget);
  });

  testWidgets('Hint sends the bare word', (t) async {
    await rig.open(t);
    await rig.tap(t, 'hint');
    expect(rig.body()['text'], 'hint');
  });

  testWidgets('the gate prefix button writes req: once', (t) async {
    await rig.open(t);
    await rig.tap(t, 'prefix');
    await rig.tap(t, 'prefix');
    final field = t.widget<TextField>(find.byKey(const ValueKey('answer')));
    expect(field.controller!.text, 'req: ');
  });

  testWidgets('Solved sends the explanation with the solved intent', (t) async {
    await rig.open(t, first: {...openData, 'state': stateWork});
    expect(
      t.widget<IconButton>(find.byKey(const ValueKey('solved'))).onPressed,
      isNull,
    );
    await rig.type(t, 'A map gives O(1) lookup.');
    await rig.tap(t, 'solved');
    expect(rig.body()['intent'], 'solved');
    expect(rig.body()['text'], 'A map gives O(1) lookup.');
  });

  testWidgets('a held turn shows its note; solved can miss a mechanism', (
    t,
  ) async {
    await rig.open(t);
    await rig.type(t, 'x = 1');
    await rig.tap(t, 'send');
    await rig.reply(t, {'held': true, 'note': 'Open the gate first'});
    expect(find.text('Open the gate first'), findsOneWidget);
    await rig.type(t, 'because');
    await rig.tap(t, 'solved');
    await rig.reply(t, {
      'reply_md': 'Close.',
      'exit': {'ok': false, 'missing': 'the ELSE branch'},
    });
    expect(find.text('the ELSE branch'), findsOneWidget);
    await rig.type(t, 'again');
    await rig.tap(t, 'send');
    expect(find.text('the ELSE branch'), findsNothing);
  });

  testWidgets('past the budget the counter turns red', (t) async {
    await rig.open(t);
    await rig.tap(t, 'hint');
    await rig.reply(t, {
      'banner': 'budget',
      'state': {
        'turns': {'used': 17, 'budget': 16, 'over': true},
      },
    });
    final text = t.widget<Text>(find.text('17/16'));
    expect(text.style!.color, isNotNull);
  });

  testWidgets('a pending question blocks a second send', (t) async {
    await rig.open(t);
    await rig.type(t, 'one');
    await rig.tap(t, 'send');
    expect(
      t.widget<IconButton>(find.byKey(const ValueKey('hint'))).onPressed,
      isNull,
    );
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
  });

  testWidgets('a statement over the limit is not sent', (t) async {
    await rig.open(t);
    await rig.type(t, 'x' * (coachMaxText + 1));
    await rig.tap(t, 'send');
    expect(rig.kind(), 'lc_open');
  });

  testWidgets('resume: the stored chat shows first, the worker replaces it', (
    t,
  ) async {
    final d = CoachDrafts(rig.kv);
    await d.saveThread(lcId, [(mine: true, md: 'cached line', grid: null)]);
    await rig.open(t, first: null, body: lcOpen(lcId: lcId));
    expect(find.text('cached line'), findsOneWidget);
    expect(rig.body(), {'lc_id': lcId});
    await rig.reply(t, {
      ...openData,
      'reply_md': null,
      'thread': [
        {'mine': false, 'md': 'from the worker'},
      ],
    });
    expect(find.text('cached line'), findsNothing);
    expect(find.text('from the worker'), findsOneWidget);
    expect((await d.thread(lcId)).single.md, 'from the worker');
  });

  testWidgets('a re-test shows the no-submit notice', (t) async {
    await rig.open(t, first: {...openData, 'retest': true});
    expect(find.textContaining('do NOT submit'), findsOneWidget);
  });

  testWidgets('a premium problem asks for the statement, then sends it', (
    t,
  ) async {
    await rig.open(t, first: null);
    await rig.reply(
      t,
      const {},
      code: 'bad_request',
      extra: {'reason': 'paste_statement'},
    );
    await t.enterText(find.byKey(const ValueKey('paste-title')), 'My problem');
    expect(
      t.widget<FilledButton>(find.byKey(const ValueKey('paste-go'))).onPressed,
      isNull,
    );
    await t.enterText(find.byKey(const ValueKey('paste-statement')), 'Count.');
    await t.pump();
    await t.pump();
    await t.ensureVisible(find.byKey(const ValueKey('paste-go')));
    await rig.tap(t, 'paste-go');
    expect(rig.body(), {'statement': 'Count.', 'title': 'My problem'});
    await rig.reply(t, openData);
    expect(find.textContaining('Restate it'), findsOneWidget);
  });

  testWidgets('a pasted statement without a title sends none', (t) async {
    await rig.open(t, first: null);
    await rig.reply(
      t,
      const {},
      code: 'bad_request',
      extra: {'reason': 'paste_statement'},
    );
    await t.enterText(find.byKey(const ValueKey('paste-statement')), 'Count.');
    await t.pump();
    await t.ensureVisible(find.byKey(const ValueKey('paste-go')));
    await rig.tap(t, 'paste-go');
    expect(rig.body(), {'statement': 'Count.'});
  });

  testWidgets('a finished session opens the post-mortem', (t) async {
    await rig.open(t);
    await rig.say(t, 'because');
    await rig.reply(t, {
      'state': {'phase': 'done'},
      'exit': {
        'ok': true,
        'summary_md': '| step | rung |\n| --- | --- |\n| 1 | H0 |',
      },
    });
    expect(find.byKey(const ValueKey('answer')), findsNothing);
    await rig.tap(t, 'postmortem');
    await t.pump(const Duration(milliseconds: 400));
    expect(find.byType(CoachPostMortemScreen), findsOneWidget);
    expect(rig.kind(), 'lc_cards');
    expect(rig.body(), {'lc_id': lcId});
    expect(find.text('rung'), findsOneWidget);
  });
}
