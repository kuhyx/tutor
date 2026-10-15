import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/session/session_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _base = 'tutor/v1/sessions/$fixtureLiveSid';

/// Feeds the screen's listens from [db] (live, meta, msgs).
Future<void> _feed(WidgetTester t, FakeRtdb db, FakeStream stream) async {
  for (final path in ['tutor/v1/live', '$_base/meta', '$_base/msgs']) {
    stream.listens[path]?.add(RtdbPut('/', getAt(db.root, path)));
    await t.pump();
  }
  await t.pump();
}

void main() {
  testWidgets('chat, answer boxes -> one message, card done -> next', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s, now: () => DateTime(2030)),
      settle: false,
    );
    expect(find.byType(CircularProgressIndicator), findsWidgets);
    await _feed(t, db, stream);
    await t.pumpAndSettle();
    expect(find.textContaining('This card: 14 min'), findsOneWidget);
    expect(find.textContaining('Stalled'), findsOneWidget);
    expect(find.text('Target card'), findsOneWidget); // wide: side inline
    expect(find.textContaining('Comprehension check'), findsOneWidget);
    expect(find.text('Send'), findsOneWidget);
    // Wheel over the margins scrolls the chat.
    final pointer = TestPointer(1, PointerDeviceKind.mouse);
    await t.sendEventToBinding(pointer.hover(const Offset(700, 30)));
    await t.sendEventToBinding(pointer.scroll(const Offset(0, -200)));
    await t.pump();

    await t.enterText(
      find.widgetWithText(TextField, 'Your answer').first,
      'power',
    );
    await t.pump();
    await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await t.sendKeyEvent(LogicalKeyboardKey.enter);
    await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0005'});
    expect(msg['kind'], 'message');
    expect(
      (msg['body'] as Map)['text'],
      contains('Q1: Which stroke makes the power?\nA: power'),
    );
    expect((msg['body'] as Map)['text'], contains('A: (skipped)'));

    // The tutor marks the card done: Next card / Stop here.
    db.root = setAt(db.root, '$_base/meta/card_done', true);
    db.root = setAt(db.root, '$_base/meta/busy', {
      'rid': '01JABCDEFGHJKMNPQRSTVWXYZ0',
      'phase': 'thinking',
      'since': 1,
      'text': 'pending words',
    });
    await _feed(t, db, stream);
    expect(find.text('pending words'), findsOneWidget);
    expect(find.text('Tutor is thinking...'), findsOneWidget);
    await t.tap(find.text('Next card'));
    await sent(t);
    final next = await answer(
      t,
      db,
      stream,
      data: {'session': '20261012-180000-aaaa'},
      settle: false, // the new session's first turn is on its way
    );
    expect(next['kind'], 'next');
    expect(next['body'], {'session': fixtureLiveSid, 'device': 'desktop'});
    expect(
      stream.listens.keys,
      contains('tutor/v1/sessions/20261012-180000-aaaa/meta'),
    );
  });

  testWidgets('phone: side panel in the drawer; mark done, switch, not_live', (
    t,
  ) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(
      t,
      SessionScreen(services: s),
      size: const Size(412, 915),
      settle: false,
    );
    await _feed(t, db, stream);
    await t.pumpAndSettle();
    expect(find.text('Target card'), findsNothing);
    await t.tap(find.byTooltip('Card and progress'));
    await t.pumpAndSettle();
    expect(find.text('intake stroke'), findsNothing);
    expect(find.text('• piston'), findsOneWidget);
    await t.tap(find.text('Mark card done'));
    await sent(t);
    final done = await answer(t, db, stream, code: 'not_live');
    expect(done['kind'], 'card_done');
    await t.tapAt(const Offset(10, 400)); // close the drawer
    await t.pumpAndSettle();
    expect(find.text('Continue this session'), findsOneWidget);
    await t.tap(find.text('Continue this session'));
    await sent(t);
    expect((await answer(t, db, stream))['kind'], 'session_resume');

    await t.tap(find.byTooltip('Card and progress'));
    await t.pumpAndSettle();
    await t.tap(find.text('Switch card'));
    await t.pumpAndSettle();
    await t.tap(find.textContaining('What opens the valves?'));
    await sent(t);
    final start = await answer(t, db, stream);
    expect(start['body'], {
      'subject': 'car',
      'card': 'eng-valves',
      'device': 'desktop',
    });
  });

  testWidgets('live session: Stop here before the card is done', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    await _feed(t, db, stream);
    await t.pumpAndSettle();
    await t.tap(find.text('Stop here'));
    await sent(t);
    final stop = await answer(t, db, stream);
    expect(stop['kind'], 'stop');
    expect(stop['body'], {'session': fixtureLiveSid});
  });

  testWidgets('no live session: Start', (t) async {
    final db = fixtureDb();
    final stream = FakeStream();
    final s = await fixtureServices(db, stream);
    await pumpScreen(t, SessionScreen(services: s), settle: false);
    stream.listens['tutor/v1/live']!.add(const RtdbPut('/', null));
    await t.pumpAndSettle();
    expect(find.text('No session yet'), findsOneWidget);
    await t.tap(find.text('Start session'));
    await sent(t);
    final start = await answer(t, db, stream);
    expect(start['kind'], 'session_start');
    // Start continues the subject's open session before a fresh card.
    expect(start['body'], {
      'subject': null,
      'card': null,
      'resume': true,
      'device': 'desktop',
    });
  });
}
