import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_queue.dart';
import 'package:tutor/mock/mock_session.dart';
import 'package:tutor/mock/mock_start_screen.dart';

import '../support/ui.dart';
import 'mock_fixtures.dart';
import 'mock_support.dart';

void main() {
  late Rig rig;
  setUp(() => rig = Rig());

  Finder key(String k) => find.byKey(ValueKey(k));

  testWidgets('time up submits drafts, finishes and opens the result', (
    t,
  ) async {
    final m = await rig.pumpTest(t);
    m.update(id: 's1', text: 'select 1');
    rig.clock = 1000000 + 3600000 + 1000;
    for (var i = 0; i < 10; i++) {
      await t.pump(const Duration(seconds: 1));
    }
    await t.pump(const Duration(milliseconds: 100));
    final bodies = mockBodies(rig.db);
    expect(bodies.map((b) => b['op']), ['answer', 'finish']);
    expect(bodies.first['answer'], 'select 1');
    expect(find.text('0:00'), findsOneWidget);
    await answer(t, rig.db, rig.stream, data: resultData);
    expect(find.text('1/4'), findsOneWidget);
    expect(find.text('25%'), findsOneWidget);
    expect(rig.kv.data['mock.active'], contains('"score":1'));
  });

  testWidgets('an app opened after time is up finishes at once', (t) async {
    rig.clock = 1000000 + 3600000 + 5000;
    await rig.pumpTest(t, settle: false);
    await t.pump(const Duration(milliseconds: 100));
    expect(mockBodies(rig.db).single['op'], 'finish');
  });

  testWidgets('Finish asks first, then grades', (t) async {
    await rig.pumpTest(t);
    await t.tap(key('finish'));
    await t.pumpAndSettle();
    expect(find.text('0/4'), findsOneWidget);
    await t.tap(key('cancel'));
    await t.pumpAndSettle();
    expect(mockBodies(rig.db), isEmpty);
    await t.tap(key('finish'));
    await t.pumpAndSettle();
    await t.tap(key('confirm'));
    await t.pump(const Duration(milliseconds: 100));
    expect(mockBodies(rig.db).single, {'op': 'finish', 'mock_id': 'm1'});
  });

  testWidgets('offline: answers stay queued and nothing is graded', (t) async {
    final m = await rig.pumpTest(t);
    rig.db.offline = true;
    await t.tap(key('opt-2'));
    await t.pumpAndSettle();
    expect(m.isSubmitted('q1'), isTrue);
    expect(await MockAnswerQueue(rig.kv).pending(), hasLength(1));
    await t.tap(key('finish'));
    await t.pumpAndSettle();
    await t.tap(key('confirm'));
    await t.pump(const Duration(milliseconds: 100));
    expect(key('unsent'), findsOneWidget);
    expect(mockBodies(rig.db), isEmpty);
    rig.db.offline = false;
    await t.tap(key('finish'));
    await t.pumpAndSettle();
    await t.tap(key('confirm'));
    await t.pump(const Duration(milliseconds: 100));
    expect(mockBodies(rig.db).map((b) => b['op']), ['answer', 'finish']);
  });

  testWidgets('a killed app resumes answers, chip and clock', (t) async {
    final m = rig.session()
      ..update(id: 'q1', text: '3', go: 2)
      ..update(id: 'p1', text: 'def f(s): return s');
    await t.pump();
    final back = await loadMockSession(
      rig.kv,
      MockAnswerQueue(rig.kv),
      relayAnswerSender(rig.s.relay),
      now: () => rig.clock,
    );
    expect(back!.answers, m.answers);
    expect(back.index, 2);
    expect(back.remaining, const Duration(minutes: 59));
    await rig.pumpTest(t, session: back);
    expect(find.textContaining('def f(s): return s'), findsWidgets);
  });

  testWidgets('a broken save is dropped', (t) async {
    rig.kv.data['mock.active'] = '{"paper": 3}';
    final back = await loadMockSession(
      rig.kv,
      MockAnswerQueue(rig.kv),
      relayAnswerSender(rig.s.relay),
    );
    expect(back, isNull);
    expect(rig.kv.data, isNot(contains('mock.active')));
  });

  testWidgets('Start sends the length and opens the test', (t) async {
    await pumpScreen(
      t,
      MockStartScreen(services: rig.s, links: rig.links),
      size: phone,
    );
    await t.tap(key('minutes-45'));
    await t.pump();
    await t.tap(key('start'));
    await t.pump(const Duration(milliseconds: 100));
    expect(mockBodies(rig.db).single, {'op': 'start', 'minutes': 45});
    await answer(t, rig.db, rig.stream, data: paperData, settle: false);
    await t.pump(const Duration(milliseconds: 500));
    expect(key('clock'), findsOneWidget);
    expect(rig.kv.data['mock.active'], contains('"mock_id":"m1"'));
  });

  testWidgets('a malformed paper is shown, not crashed on', (t) async {
    await pumpScreen(
      t,
      MockStartScreen(services: rig.s, links: rig.links),
      size: phone,
    );
    await t.tap(key('start'));
    await t.pump(const Duration(milliseconds: 100));
    await answer(t, rig.db, rig.stream, data: {'mock_id': 'x'});
    expect(find.textContaining('started_ms'), findsOneWidget);
  });
}
