import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/drill/drill_models.dart';
import 'package:tutor/ui/read_screen.dart';
import 'package:tutor/widgets/cue_chip.dart';

import '../support/drill.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/fit.dart';
import '../support/label_finders.dart';
import '../support/learn_finders.dart';
import '../support/no_words.dart';
import '../support/read.dart';
import '../support/ui.dart';

/// Opens read mode on a phone; [card] answers the first `read_next`.
Future<(FakeRtdb, FakeStream)> _open(
  WidgetTester t, {
  Map<String, Object?>? card,
  Unavailable? unavailable,
  VoidCallback? onFreeChat,
  String? subject,
}) async {
  final db = fixtureDb();
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    ReadScreen(
      services: s,
      subject: subject,
      unavailable: unavailable,
      onFreeChat: onFreeChat,
    ),
    size: kPhone,
    settle: false,
  );
  final asked = await answer(t, db, stream, data: card ?? readCard());
  expect(asked['kind'], 'read_next');
  expect(asked['body'], {'subject': subject});
  return (db, stream);
}

Finder get _again => spoken('Again');
Finder get _gotIt => spoken('Got it');

void main() {
  testWidgets('front -> flip -> got it -> the next card', (t) async {
    final (db, stream) = await _open(t, subject: 'car');
    expect(find.text('What does the crankshaft do?'), findsOne);
    expect(find.textContaining('turns the pistons'), findsNothing);
    expect(_gotIt, findsNothing);
    expect(spoken('Read: 0'), findsOne);
    expect(wordsOnScreen(t), isEmpty);
    expectFits(t);
    // Tapping the card body flips it.
    await t.tap(find.text('What does the crankshaft do?'));
    await t.pumpAndSettle();
    expect(find.textContaining('turns the pistons'), findsOne);
    expect(find.textContaining('translates reciprocating'), findsOne);
    expect(find.text('en.wikipedia.org'), findsOne);
    expect(find.byIcon(Icons.link), findsOne);
    expect(spoken('Flip card'), findsNothing);
    expect(wordsOnScreen(t), isEmpty);
    expectFits(t);
    await t.tap(_gotIt);
    await sent(t);
    final rated = await answer(t, db, stream, data: readRated('got_it'));
    expect(rated['kind'], 'read_rate');
    expect(rated['body'], {'prompt_id': readPromptId(), 'rating': 'got_it'});
    await sent(t);
    final next = await answer(
      t,
      db,
      stream,
      data: readCard(id: 'eng-valve', front: 'Q2'),
    );
    expect(next['kind'], 'read_next');
    expect(find.text('Q2'), findsOne);
    expect(_gotIt, findsNothing);
    expect(spoken('Read: 1'), findsOne);
  });

  testWidgets('the flip glyph flips; again rates again', (t) async {
    final (db, stream) = await _open(t);
    await t.tap(spoken('Flip card'));
    await t.pumpAndSettle();
    expect(_again, findsOne);
    await t.tap(_again);
    await sent(t);
    final rated = await answer(t, db, stream, data: readRated('again'));
    expect(rated['body'], {'prompt_id': readPromptId(), 'rating': 'again'});
    await sent(t);
    await answer(t, db, stream, data: readCard(front: 'Q2'));
    expect(find.text('Q2'), findsOne);
  });

  testWidgets('nothing left: one inbox glyph, no words', (t) async {
    await _open(t, card: {'empty': true});
    expect(find.byIcon(Icons.inbox_outlined), findsOne);
    expect(spokenHas('Nothing left to read'), findsOne);
    expect(_again, findsNothing);
    expect(wordsOnScreen(t), isEmpty);
    expectFits(t);
  });

  testWidgets('phone 412x915: a long back pages, the rate bar stays', (
    t,
  ) async {
    final long = 'A long answer about crankshafts and pistons. ' * 30;
    final quote = 'A long quoted excerpt from the source page. ' * 30;
    await _open(
      t,
      card: readCard(back: long, excerpt: quote),
    );
    await t.tap(spoken('Flip card'));
    await t.pumpAndSettle();
    expectFits(t);
    for (final b in [_again, _gotIt]) {
      final r = t.getRect(b);
      expect(r.bottom, lessThanOrEqualTo(kPhone.height));
      expect(r.height, greaterThanOrEqualTo(56));
    }
    expect(find.byKey(const ValueKey('fit-next')), findsOne);
  });

  testWidgets('outage glyph from the screen, then the PC wins', (t) async {
    final freeChats = <int>[];
    final (db, stream) = await _open(
      t,
      unavailable: const Unavailable(until: kResetsAt, reason: 'limit'),
      onFreeChat: () => freeChats.add(1),
      card: readCard(unavailable: {'until': kResetsAt, 'reason': 'network'}),
    );
    expect(find.byIcon(Icons.wifi_off), findsOne);
    expect(spoken('Claude limit — back at ${hhmm(kResetsAt)}'), findsOne);
    await t.tap(spoken('Free chat'));
    expect(freeChats, [1]);
    // The PC says Claude is back: the glyph goes.
    await t.tap(spoken('Flip card'));
    await t.pumpAndSettle();
    await t.tap(_gotIt);
    await sent(t);
    await answer(t, db, stream, data: readRated('got_it'));
    await sent(t);
    await answer(t, db, stream, data: readCard(front: 'Q2'));
    expect(find.byIcon(Icons.wifi_off), findsNothing);
  });

  testWidgets('keys: 2 before a flip does nothing; Space, 1, Enter, 2', (
    t,
  ) async {
    final (db, stream) = await _open(t);
    expect(spoken('Free chat'), findsNothing);
    expect(find.byIcon(Icons.hourglass_bottom), findsNothing);
    final (rid, _) = lastRequest(db);
    await t.sendKeyEvent(LogicalKeyboardKey.digit2);
    await sent(t);
    expect(lastRequest(db).$1, rid);
    await t.sendKeyEvent(LogicalKeyboardKey.space);
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.digit1);
    await sent(t);
    final again = await answer(t, db, stream, data: readRated('again'));
    expect(again['body'], {'prompt_id': readPromptId(), 'rating': 'again'});
    await sent(t);
    await answer(
      t,
      db,
      stream,
      data: readCard(id: 'b', front: 'Q2'),
    );
    await t.sendKeyEvent(LogicalKeyboardKey.enter);
    await t.pumpAndSettle();
    await t.sendKeyEvent(LogicalKeyboardKey.digit2);
    await sent(t);
    final got = await answer(t, db, stream, data: readRated('got_it'));
    expect(got['body'], {'prompt_id': readPromptId('b'), 'rating': 'got_it'});
  });

  testWidgets('a failed rate retries; a gone prompt asks for the next', (
    t,
  ) async {
    final (db, stream) = await _open(t);
    await t.tap(spoken('Flip card'));
    await t.pumpAndSettle();
    await t.tap(_gotIt);
    await sent(t);
    await answer(t, db, stream, code: 'worker_error');
    expect(cueOfKind(CueKind.error), findsOne);
    await t.tap(spoken('Retry'));
    await sent(t);
    final again = await answer(t, db, stream, code: 'unknown_prompt');
    expect(again['kind'], 'read_rate');
    await t.tap(spoken('Retry'));
    await sent(t);
    final next = await answer(t, db, stream, data: {'foo': 1});
    expect(next['kind'], 'read_next');
    expect(cueLabelled('Unreadable reply', prefix: true), findsOne);
    await t.tap(spoken('Retry'));
    await sent(t);
    await answer(t, db, stream, data: readCard(front: 'Q2'));
    expect(find.text('Q2'), findsOne);
    // A rate while offline: Retry sends it again.
    await t.tap(spoken('Flip card'));
    await t.pumpAndSettle();
    db.failPrefix = '/tutor/v1-e2e/requests';
    await t.tap(_gotIt);
    await t.pumpAndSettle();
    expect(cueLabelled('Not sent: no connection', prefix: true), findsOne);
    db.failPrefix = null;
    await t.tap(spoken('Retry'));
    await sent(t);
    expect(lastRequest(db).$2['kind'], 'read_rate');
    // The requests listen ends with no result.
    unawaited(stream.listens['tutor/v1-e2e/requests']!.close());
    await t.pumpAndSettle();
    expect(cueLabelled('The PC did not answer.'), findsOne);
  });
}
