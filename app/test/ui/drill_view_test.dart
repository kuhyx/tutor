import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/anki_sync.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/ui/review_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/drill.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/ui.dart';

/// Opens the drill on a phone-sized window; the first question is answered.
Future<(FakeRtdb, FakeStream)> _open(
  WidgetTester t, {
  Unavailable? unavailable,
  Map<String, Object?>? question,
  bool android = false,
}) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    ReviewScreen(
      services: s,
      drill: true,
      unavailable: unavailable,
      anki: AnkiSync(
        relay: s.relay,
        launcher: FakeLauncher(supported: android),
      ),
    ),
    size: kPhone,
    settle: false,
  );
  if (question != null) {
    await answer(t, db, stream, data: question);
  }
  return (db, stream);
}

void main() {
  testWidgets('tap a wrong option: marked, back, source, Next; no scroll', (
    t,
  ) async {
    final (db, stream) = await _open(t, question: drillQuestion());
    expect(spoken('Today: 23 min credited'), findsOne);
    expect(find.text('What does the crankshaft do?'), findsOne);
    expect(find.byType(TextField), findsNothing);
    final first = find.widgetWithText(OutlinedButton, 'Opens valves');
    expect(t.getSize(first).height, greaterThanOrEqualTo(56));
    await t.tap(first);
    await sent(t);
    final pick = await answer(t, db, stream, data: drillGrade(0));
    expect(pick['kind'], 'drill_answer');
    expect(pick['body'], {'prompt_id': 'p1', 'choice': 0});
    expect(spoken('Not quite'), findsOne);
    expect(find.byIcon(Icons.close), findsOne);
    expect(find.byIcon(Icons.check), findsOne);
    expect(find.textContaining('turns the pistons'), findsOne);
    expect(find.textContaining('translates reciprocating'), findsOne);
    expect(find.text('en.wikipedia.org'), findsOne);
    expect(spoken('Today: 23 min credited'), findsOne);
    // Everything on one screen: nothing scrolls, one page.
    expectFits(t);
    expect(find.byKey(const ValueKey('fit-next')), findsNothing);
    await t.tap(spoken('Next (Space)'));
    await sent(t);
    final next = await answer(t, db, stream, data: drillQuestion(front: 'Q2'));
    expect(next['kind'], 'drill_next');
    expect(find.text('Q2'), findsOne);
    expect(spoken('Not quite'), findsNothing);
  });

  testWidgets('a long excerpt pages; Next stays on screen', (t) async {
    final (db, stream) = await _open(t, question: drillQuestion());
    await t.tap(find.widgetWithText(OutlinedButton, 'Opens valves'));
    await sent(t);
    final long = 'A long quoted excerpt from the source page. ' * 40;
    await answer(t, db, stream, data: {...drillGrade(0), 'excerpt': long});
    expectFits(t);
    expect(find.byKey(const ValueKey('fit-next')), findsOne);
    final next = spoken('Next (Space)');
    expect(t.getRect(next).bottom, lessThanOrEqualTo(kPhone.height));
    await t.tap(next);
    await sent(t);
    final asked = await answer(t, db, stream, data: drillQuestion(front: 'Q2'));
    expect(asked['kind'], 'drill_next');
  });

  testWidgets('Android: the Sync row sits in the header; still no scroll', (
    t,
  ) async {
    final (db, stream) = await _open(
      t,
      android: true,
      question: {
        ...drillQuestion(),
        'options': ['One', 'Two', 'Three', 'Four'],
      },
    );
    expect(spoken('Sync Anki & credit'), findsOne);
    await t.tap(find.text('One'));
    await sent(t);
    await answer(t, db, stream, data: drillGrade(0));
    expect(spoken('Next (Space)'), findsOne);
    // Measured with the test font (every glyph a full square, so wider
    // than real text): the real-font check is the fixture screenshot.
    expectFits(t);
    expect(find.byKey(const ValueKey('fit-next')), findsNothing);
  });

  testWidgets('keys: 2 picks the right option, Space asks for the next', (
    t,
  ) async {
    final (db, stream) = await _open(t, question: drillQuestion());
    await t.sendKeyEvent(LogicalKeyboardKey.digit2);
    await sent(t);
    await answer(t, db, stream, data: drillGrade(1));
    expect(spoken('Correct · +1 min credited'), findsOne);
    expect(spoken('Today: 24 min credited'), findsOne);
    expect(find.byIcon(Icons.close), findsNothing);
    // A second pick on an answered question does nothing.
    await t.sendKeyEvent(LogicalKeyboardKey.digit1);
    await t.pump();
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await sent(t);
    final next = await answer(t, db, stream, data: drillQuestion(front: 'Q2'));
    expect(next['kind'], 'drill_next');
    // Space with nothing answered does nothing.
    await t.sendKeyEvent(LogicalKeyboardKey.enter);
    await t.pump();
    expect(find.text('Q2'), findsOne);
  });

  testWidgets('banner: from the screen, then from the question', (t) async {
    final (db, stream) = await _open(
      t,
      unavailable: const Unavailable(until: kResetsAt, reason: 'limit'),
    );
    final banner = 'Claude limit — back at ${hhmm(kResetsAt)}';
    expect(spoken(banner), findsOne);
    await answer(
      t,
      db,
      stream,
      data: drillQuestion(unavailable: {'until': kResetsAt}),
    );
    // The PC's answer wins; no reason reads "Claude unavailable".
    expect(spoken(banner), findsNothing);
    expect(
      spoken('Claude unavailable — back at ${hhmm(kResetsAt)}'),
      findsOne,
    );
    // The time is painted as digits; no sentence.
    expect(find.text(hhmm(kResetsAt)), findsOne);
  });

  testWidgets('empty, then failures offer Retry', (t) async {
    final (db, stream) = await _open(t);
    await answer(t, db, stream, data: {'empty': true});
    expect(spokenHas('Nothing to drill'), findsOne);
    await t.tap(spoken('Review'));
    await t.pumpAndSettle();
    await t.tap(spoken('Drill').last);
    await sent(t);
    await answer(t, db, stream, code: 'worker_error');
    expect(cueLabelled('Something broke on the PC', prefix: true), findsOne);
    expect(cueOfKind(CueKind.error), findsOne);
    await t.tap(spoken('Retry'));
    await sent(t);
    await answer(t, db, stream, data: {'foo': 1});
    expect(cueLabelled('Unreadable reply', prefix: true), findsOne);
    await t.tap(spoken('Retry'));
    await sent(t);
    // The requests listen ends with no result.
    unawaited(stream.listens['tutor/v1/requests']!.close());
    await t.pumpAndSettle();
    expect(cueLabelled('The PC did not answer.'), findsOne);
    await t.tap(spoken('Retry'));
    await sent(t);
    await answer(t, db, stream, data: drillQuestion());
    expect(find.text('What does the crankshaft do?'), findsOne);
    // A pick while offline: the question is kept, Retry sends it again.
    db.failPrefix = '/tutor/v1/requests';
    await t.tap(find.text('Opens valves'));
    await t.pumpAndSettle();
    expect(cueLabelled('Not sent: no connection', prefix: true), findsOne);
    db.failPrefix = null;
    await t.tap(spoken('Retry'));
    await sent(t);
    await answer(t, db, stream, data: drillGrade(1));
    expect(spoken('Correct · +1 min credited'), findsOne);
  });

  testWidgets('Review and Drill switch inside one screen', (t) async {
    final (db, stream) = await _open(t, question: drillQuestion());
    expect(spoken('Review'), findsOne);
    await t.tap(spoken('Review'));
    await t.pumpAndSettle();
    expect(spokenHas('Nothing due'), findsOne);
    expect(spoken('Drill'), findsWidgets);
    expect(db.root, isNotNull);
    expect(stream.listens, isNotEmpty);
  });
}
