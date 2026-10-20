// The app's long-lived RTDB streams per screen state stay at 4 or fewer.
//
// RTDB speaks HTTP/1.1 only (the production host never negotiates h2), so
// Chrome gives it 6 connections, and every stream holds one for good. With
// 6 streams open a Send's PUT never got a socket and the session sat on
// "Sent; waiting for the PC..." (2026-10-20). 4 leaves 2 for writes and
// one-off reads. The flows run through the real route stack, Home at the
// root, at a wide and a phone size.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/app/services.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/home_screen.dart';
import 'package:tutor/ui/nav.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

/// The most streams the app may hold at once.
const maxStreams = 4;

const _base = 'tutor/v1/sessions/$fixtureLiveSid';
const _old = '20261011-090000-a1b2';
const _wide = Size(1366, 1500);
const _phone = Size(412, 915);

/// Answers every open data listen with its snapshot, as RTDB does on
/// connect, until no new listen opens (live names the session to follow).
Future<void> _sync(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  for (var round = 0; round < 3; round++) {
    for (final path in stream.openPaths) {
      if (path.contains('/requests')) continue; // answered by answer()
      stream.listens[path]!.add(RtdbPut('/', getAt(db.root, path)));
    }
    await t.pump();
  }
  await t.pump(const Duration(milliseconds: 50));
}

const _rev = 'tutor/v1/rev';
const _workers = 'tutor/v1/presence/workers';
const _live = 'tutor/v1/live';
const _requests = 'tutor/v1/requests';

/// Exactly [paths] are open now.
void _holds(FakeStream stream, Set<String> paths) =>
    expect(stream.openPaths.toSet(), paths);

void _within(FakeStream stream, String state) => expect(
  stream.peak,
  lessThanOrEqualTo(maxStreams),
  reason: '$state: ${stream.peak} streams open: ${stream.peakPaths}',
);

Future<(FakeRtdb, FakeStream, TutorServices)> _home(
  WidgetTester t,
  Size size, {
  bool cardDone = false,
}) async {
  debugPhone = size == _phone;
  addTearDown(() => debugPhone = false);
  final db = fixtureDb();
  if (cardDone) db.root = setAt(db.root, '$_base/meta/card_done', true);
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(
    t,
    HomeScreen(services: s, onSignedOut: () {}),
    size: size,
  );
  await _sync(t, db, stream);
  _within(stream, 'Home');
  return (db, stream, s);
}

/// Lets a route transition finish (a spinner never settles).
Future<void> _settle(WidgetTester t) async {
  for (var i = 0; i < 12; i++) {
    await t.pump(const Duration(milliseconds: 50));
  }
}

BuildContext _top(WidgetTester t) =>
    t.element(find.byType(Scaffold, skipOffstage: false).last);

final Finder _answerBox = find.byWidgetPredicate(
  (w) =>
      w is TextField &&
      (w.decoration?.labelText ?? '').startsWith('Your answer'),
);

/// Types into the first answer box and taps Send; the turn is in flight.
Future<void> _send(WidgetTester t, String text) async {
  final send = find.widgetWithText(FilledButton, 'Send');
  // The phone pages through the questions: Next until the last one.
  for (var page = 0; page < 5; page++) {
    await t.enterText(_answerBox.first, text);
    await t.pump();
    if (send.evaluate().isNotEmpty) break;
    await t.tap(find.widgetWithText(FilledButton, 'Next'));
    await _settle(t);
  }
  await t.ensureVisible(send);
  await t.pump();
  await t.tap(send);
  await sent(t);
}

void main() {
  for (final size in [_wide, _phone]) {
    final label = size == _phone ? 'phone' : 'wide';

    testWidgets('$label: Session idle, a turn in flight, its reply', (t) async {
      final (db, stream, s) = await _home(t, size);
      unawaited(openSession(_top(t), s));
      await _settle(t);
      await _sync(t, db, stream);
      _within(stream, 'Session idle');
      _holds(stream, {_rev, _workers, _live, _base});
      await _send(t, 'power');
      await _sync(t, db, stream);
      _within(stream, 'Session, turn in flight');
      // The request's listen took rev's connection.
      _holds(stream, {_workers, _live, _base, _requests});
      await answer(t, db, stream, data: {'msg': 'm0005'}, settle: false);
      await _sync(t, db, stream);
      _within(stream, 'Session, reply in');
      _holds(stream, {_rev, _workers, _live, _base});
    });

    testWidgets('$label: card end, a follow-up in flight', (t) async {
      final (db, stream, s) = await _home(t, size, cardDone: true);
      unawaited(openSession(_top(t), s));
      await _settle(t);
      await _sync(t, db, stream);
      expect(find.text('Next card'), findsWidgets);
      _within(stream, 'Session at card end');
      await _send(t, 'what if I forge it?');
      await _sync(t, db, stream);
      _within(stream, 'card end, follow-up in flight');
    });

    testWidgets('$label: History, Ask a follow-up, then its Session', (
      t,
    ) async {
      final (db, stream, s) = await _home(t, size);
      db.root = setAt(db.root, 'tutor/v1/sessions/$_old/msgs', {
        'm0001': {'role': 'tutor', 'text': 'Card done.'},
      });
      unawaited(openHistory(_top(t), s));
      await _settle(t);
      unawaited(openTranscript(_top(t), s, _old));
      await _settle(t);
      _within(stream, 'transcript');
      await t.enterText(
        find.widgetWithText(TextField, 'Ask a follow-up'),
        'what if I write the name myself?',
      );
      await t.tap(find.text('Ask'));
      await sent(t);
      _within(stream, 'follow_up_open in flight');
      await answer(t, db, stream, data: {'session': _old}, settle: false);
      await sent(t);
      _within(stream, 'follow-up message in flight');
      await answer(t, db, stream, data: {'msg': 'm0003'}, settle: false);
      await _settle(t);
      await _sync(t, db, stream);
      _within(stream, 'the follow-up Session');
    });

    testWidgets('$label: a Home request still in flight under a turn', (
      t,
    ) async {
      final (db, stream, s) = await _home(t, size);
      final field = find.widgetWithText(TextField, 'I want to learn...');
      await t.ensureVisible(field);
      await t.enterText(field, 'how a boat floats');
      await t.ensureVisible(find.text('Draft a plan'));
      await t.pump();
      await t.tap(find.text('Draft a plan'));
      await sent(t);
      _within(stream, 'Home, subject_new in flight');
      unawaited(openSession(_top(t), s));
      await _settle(t);
      await _sync(t, db, stream);
      await _send(t, 'power');
      await _sync(t, db, stream);
      _within(stream, 'Session turn over a Home request');
      // Both requests share one listen.
      _holds(stream, {_workers, _live, _base, _requests});
    });
  }
}
