import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/model/request.dart';
import 'package:tutor/model/request_body.dart';
import 'package:tutor/relay/error_text.dart';
import 'package:tutor/sync/json_tree.dart';
import 'package:tutor/sync/rtdb_event.dart';
import 'package:tutor/ui/transcript_screen.dart';
import 'package:tutor/util/device.dart';

import '../../tool/fixture/fixture_sessions.dart';
import '../support/composer.dart';
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/label_finders.dart';
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
  tearDown(() => debugPhone = false);

  test('follow_up_open is a chat kind with the session only', () {
    expect(RequestKind.parse('follow_up_open'), RequestKind.followUpOpen);
    expect(RequestKind.followUpOpen.lane, Lane.chat);
    final body = RequestBody.followUpOpen('s1').withDevice('phone');
    expect(body.body, {'session': 's1'});
    // Was the app's one coverage gap (no test built a lift_cap start).
    expect(RequestBody.sessionStart(liftCap: true).body['lift_cap'], isTrue);
    expect(
      kindText('err_session_live', 'session_live'),
      'Another session is live.',
    );
  });

  testWidgets('card end: Next card, Stop here and a follow-up composer', (
    t,
  ) async {
    final (db, stream) = await openComposer(t, phone: false, questions: false);
    db.root = setAt(db.root, '$composeBase/meta/card_done', true);
    stream.emit(
      '$composeBase/meta',
      RtdbPut('/', getAt(db.root, '$composeBase/meta')),
    );
    await t.pumpAndSettle();
    expect(controlByLabel('Next card'), findsOneWidget);
    // Wide: the side panel's Stop here and the card end's, as before.
    expect(controlByLabel('Stop here'), findsWidgets);
    expect(controlByLabel('Send'), findsOneWidget);
    final box = fieldByLabel(
      'Your answer. Reason it out; guesses are welcome.',
    );
    expect(box, findsOneWidget);
    await t.enterText(box, 'what if I forge it?');
    await t.ensureVisible(controlByLabel('Send'));
    await t.pump();
    await t.tap(controlByLabel('Send'));
    await sent(t);
    final msg = await answer(t, db, stream, data: {'msg': 'm0009'});
    expect(msg['kind'], 'message');
    expect((msg['body'] as Map)['text'], 'what if I forge it?');
    expect((msg['body'] as Map)['session'], fixtureLiveSid);
  });

  testWidgets('phone, keyboard open: card end buttons and Send fit', (t) async {
    final (db, stream) = await openComposer(t, phone: true, questions: false);
    db.root = setAt(db.root, '$composeBase/meta/card_done', true);
    stream.emit(
      '$composeBase/meta',
      RtdbPut('/', getAt(db.root, '$composeBase/meta')),
    );
    t.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(t.view.resetViewInsets);
    await t.pumpAndSettle();
    for (final label in ['Next card', 'Stop here', 'Send']) {
      expect(
        controlByLabel(label).hitTestable(),
        findsOneWidget,
        reason: label,
      );
    }
  });

  testWidgets('history: ask a follow-up reopens, sends, opens the session', (
    t,
  ) async {
    final (db, stream) = await _transcript(t, _old);
    expect(fieldByLabel('Ask a follow-up'), findsOneWidget);
    await t.enterText(
      fieldByLabel('Ask a follow-up'),
      'what if I write the name myself?',
    );
    await t.tap(controlByLabel('Ask'));
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
    expect(
      cueLabelled('Another session is live.', prefix: true),
      findsOneWidget,
    );
    expect(find.text('what if I write the name myself?'), findsOneWidget);

    await t.tap(controlByLabel('Ask'));
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
    expect(bySpoken('Target card'), findsWidgets); // replaced by Session
  });

  testWidgets('history: no follow-up for a card not done there', (t) async {
    await _transcript(t, _older);
    expect(bySpoken('Ask a follow-up'), findsNothing);
  });
}
