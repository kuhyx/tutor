import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/transcript_screen.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/composer.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/ui.dart';

const _old = '20261011-090000-a1b2';
const _older = '20261010-200000-c3d4';

/// The transcript screen of [sid] (its messages set to one tutor turn).
Future<(FakeRtdb, FakeStream)> _transcript(WidgetTester t, String sid) async {
  final db = fixtureDb();
  db.root = setAt(db.root, 'tutor/v1/sessions/$sid/msgs', {
    'm0001': {'role': 'tutor', 'text': 'Card done.'},
  });
  final stream = FakeStream();
  final s = await fixtureServices(db, stream);
  await pumpScreen(t, TranscriptScreen(services: s, sid: sid));
  return (db, stream);
}

void main() {
  test('follow_up_open is a chat kind with the session only', () {
    expect(RequestKind.parse('follow_up_open'), RequestKind.followUpOpen);
    expect(RequestKind.followUpOpen.lane, Lane.chat);
    final body = RequestBody.followUpOpen('s1').withDevice('phone');
    expect(body.body, {'session': 's1'});
    // Was the app's one coverage gap (no test built a lift_cap start).
    expect(RequestBody.sessionStart(liftCap: true).body['lift_cap'], isTrue);
    expect(
      errorText('session_live', 'stop the current session first'),
      'Another session is live. stop the current session first',
    );
  });

  testWidgets('card end: Next card, Stop here and a follow-up composer', (
    t,
  ) async {
    final (db, stream) = await openComposer(t, phone: false, questions: false);
    db.root = setAt(db.root, '$composeBase/meta/card_done', true);
    stream.listens['$composeBase/meta']!.add(
      RtdbPut('/', getAt(db.root, '$composeBase/meta')),
    );
    await t.pumpAndSettle();
    expect(find.text('Next card'), findsOneWidget);
    expect(find.text('Stop here'), findsWidgets);
    expect(find.text('Send'), findsOneWidget);
    final box = find.widgetWithText(
      TextField,
      'Your answer. Reason it out; guesses are welcome.',
    );
    expect(box, findsOneWidget);
    await t.enterText(box, 'what if I forge it?');
    await t.ensureVisible(find.text('Send'));
    await t.pump();
    await t.tap(find.text('Send'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0009'});
    expect(msg['kind'], 'message');
    expect((msg['body'] as Map)['text'], 'what if I forge it?');
    expect((msg['body'] as Map)['session'], fixtureLiveSid);
  });

  testWidgets('history: ask a follow-up reopens, sends, opens the session', (
    t,
  ) async {
    final (db, stream) = await _transcript(t, _old);
    expect(find.text('Ask a follow-up'), findsOneWidget);
    await t.enterText(
      find.widgetWithText(TextField, 'Ask a follow-up'),
      'what if I write the name myself?',
    );
    await t.tap(find.text('Ask'));
    await sent(t);
    // Another session is live: refused, the question stays in the box.
    final refused = await answer(
      t,
      db,
      stream,
      code: 'session_live',
      error: 'stop the current session first',
    );
    expect(refused['kind'], 'follow_up_open');
    expect(refused['body'], {'session': _old});
    expect(find.textContaining('Another session is live.'), findsOneWidget);
    expect(find.text('what if I write the name myself?'), findsOneWidget);

    await t.tap(find.text('Ask'));
    await sent(t);
    await answer(t, db, stream, data: {'session': _old}, settle: false);
    await sent(t);
    final asked = await answer(
      t,
      db,
      stream,
      data: {'msg': 'm0003'},
      settle: false,
    );
    expect(asked['kind'], 'message');
    expect(asked['body'], {
      'session': _old,
      'text': 'what if I write the name myself?',
      'device': 'desktop',
    });
    expect(find.text('Target card'), findsOneWidget); // replaced by Session
  });

  testWidgets('history: no follow-up for a card not done there', (t) async {
    await _transcript(t, _older);
    expect(find.text('Ask a follow-up'), findsNothing);
  });
}
