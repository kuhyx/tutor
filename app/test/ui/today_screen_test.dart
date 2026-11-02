import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/plan/today_plan.dart';
import 'package:tutor/ui/coach/coach_screen.dart';
import 'package:tutor/ui/today_screen.dart';

import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/services.dart';
import '../support/ui.dart';

Map<String, Object?> _wire({int done = 0}) => {
  'date': '2026-11-03',
  'steps': [
    for (var i = 1; i <= 3; i++)
      {
        'id': 's$i',
        'title': 'Step title $i',
        'what': 'Do thing $i.',
        'kind': i == 3 ? 'note' : 'coach',
        if (i < 3) 'target': 'slug-$i',
        'done': i <= done,
      },
  ],
  'current': 's${done + 1}',
};

void main() {
  test('parses, skips unknown kinds, finds the current step', () {
    final plan = TodayPlan.fromJson({
      'date': 'd',
      'steps': [
        {'id': 'a', 'title': 'A', 'kind': 'coach', 'done': true},
        {'id': 'x', 'title': 'X', 'kind': 'teleport'},
        {'id': 'b', 'title': 'B', 'kind': 'sql_lesson', 'target': 'dates'},
      ],
    });
    expect(plan.steps.map((s) => s.id), ['a', 'b']);
    expect(plan.current?.id, 'b');
    expect(plan.current?.kind, StepKind.sqlLesson);
    expect(plan.doneCount, 1);
    expect(TodayPlan.fromJson({'date': 'd'}).steps, isEmpty);
  });

  group('screen', () {
    late FakeRtdb db;
    late FakeStream stream;

    Future<void> open(WidgetTester t, {int done = 0}) async {
      db = FakeRtdb();
      stream = FakeStream();
      final s = services(db, stream);
      addTearDown(s.focus.dispose);
      await pumpScreen(
        t,
        TodayScreen(
          services: s,
          plan: TodayPlan.fromJson(_wire(done: done)),
          openHome: () {},
        ),
        size: const Size(400, 800),
        settle: false,
      );
      await sent(t);
    }

    testWidgets('shows the first step only, with Start and Done', (t) async {
      await open(t);
      expect(find.text('Step title 1'), findsOneWidget);
      expect(find.text('Do thing 1.'), findsOneWidget);
      expect(find.text('Step title 2'), findsNothing);
      expect(find.byKey(const ValueKey('today-start')), findsOneWidget);
      expect(find.byKey(const ValueKey('today-home')), findsOneWidget);
    });

    testWidgets('Start opens the coach on the step target', (t) async {
      await open(t);
      await t.tap(find.byKey(const ValueKey('today-start')));
      await sent(t);
      final screen = t.widget<CoachScreen>(find.byType(CoachScreen));
      expect(screen.open.body['problem'], 'slug-1');
    });

    testWidgets('Done sends plan_step_done and shows the next step', (t) async {
      await open(t);
      await t.tap(find.byKey(const ValueKey('today-done')));
      await sent(t);
      final (_, req) = lastRequest(db);
      expect(req['kind'], 'plan_step_done');
      expect((req['body'] as Map)['id'], 's1');
      await answer(t, db, stream, data: _wire(done: 1));
      expect(find.text('Step title 2'), findsOneWidget);
    });

    testWidgets('a note step has no Start; all done says so', (t) async {
      await open(t, done: 2);
      expect(find.text('Step title 3'), findsOneWidget);
      expect(find.byKey(const ValueKey('today-start')), findsNothing);
      await t.tap(find.byKey(const ValueKey('today-done')));
      await sent(t);
      await answer(t, db, stream, data: _wire(done: 3));
      expect(find.byKey(const ValueKey('today-all-done')), findsOneWidget);
    });
  });
}
