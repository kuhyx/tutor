import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_entry.dart';
import 'package:tutor/mock/mock_links.dart';
import 'package:tutor/mock/mock_result_screen.dart';
import 'package:tutor/ui/coach/coach_screen.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';

import '../support/fit.dart';
import '../support/ui.dart';
import 'mock_fixtures.dart';
import 'mock_support.dart';

void main() {
  late Rig rig;
  setUp(() => rig = Rig());

  Finder key(String k) => find.byKey(ValueKey(k));

  Future<void> pumpResult(WidgetTester t) async {
    final m = rig.session()..finished(resultData);
    await pumpScreen(
      t,
      MockResultScreen(services: rig.s, session: m, links: rig.links),
      size: phone,
    );
  }

  testWidgets('score, percent and a verdict per task', (t) async {
    await pumpResult(t);
    expect(find.text('1/4'), findsOneWidget);
    expect(find.text('25%'), findsOneWidget);
    expect(find.byIcon(Icons.cancel), findsWidgets);
  });

  testWidgets('missed items open with their detail', (t) async {
    await pumpResult(t);
    expect(key('mark-0-0'), findsOneWidget);
    expect(find.text('Bob'), findsOneWidget);
    expect(find.text('1/3'), findsOneWidget);
    expect(key('example-2-bad'), findsOneWidget);
    expect(key('option-1'), findsOneWidget);
    await t.tap(key('item-q1'));
    await t.pumpAndSettle();
    expect(find.text('[2, 1]'), findsWidgets);
  });

  testWidgets('a failed SQL item shows its database error as content', (
    t,
  ) async {
    final data = jsonDecode(jsonEncode(resultData)) as Map<String, dynamic>;
    for (final i in data['tasks'] as List<dynamic>) {
      final item = i as Map<String, dynamic>;
      if (item['section'] == 'sql') {
        item['detail'] = {'error': 'syntax boom'};
      }
    }
    final m = rig.session()..finished(data);
    await pumpScreen(
      t,
      MockResultScreen(services: rig.s, session: m, links: rig.links),
      size: phone,
    );
    expect(find.text('syntax boom'), findsOneWidget);
  });

  testWidgets('only missed items with a link get a study button', (t) async {
    await pumpResult(t);
    expect(key('study-q2'), findsNothing);
    expect(key('study-q1'), findsNothing);
    await pageTo(t, key('study-p1'));
    await t.tap(key('study-p1'));
    await pageTo(t, key('study-s1'));
    await t.tap(key('study-s1'));
    expect(rig.opened, [
      'coach:longest-palindromic-substring',
      'lesson:joins-null',
    ]);
  });

  testWidgets('Done forgets the saved test', (t) async {
    await pumpResult(t);
    await rig.kv.set('mock.active', 'x');
    await t.tap(key('done'));
    await t.pumpAndSettle();
    expect(rig.kv.data, isNot(contains('mock.active')));
  });

  Future<void> host(WidgetTester t) => pumpScreen(
    t,
    Builder(
      builder: (c) => Scaffold(
        body: TextButton(
          key: const ValueKey('open'),
          onPressed: () => openMock(c, rig.s, links: rig.links),
          child: const Icon(Icons.quiz),
        ),
      ),
    ),
    size: phone,
  );

  testWidgets('opening with nothing saved starts fresh', (t) async {
    await host(t);
    await t.tap(key('open'));
    await t.pumpAndSettle();
    expect(key('start'), findsOneWidget);
  });

  testWidgets('opening a running test resumes it', (t) async {
    final now = DateTime.now().millisecondsSinceEpoch;
    rig
        .session(
          paper: {
            ...paperData,
            'started_ms': now,
            'deadline_ms': now + 3600000,
          },
        )
        .update(id: 'q1', text: '2');
    await host(t);
    await t.tap(key('open'));
    await t.pumpAndSettle();
    expect(key('clock'), findsOneWidget);
  });

  testWidgets('opening a finished test shows its result', (t) async {
    rig.session().finished(resultData);
    await host(t);
    await t.tap(key('open'));
    await t.pumpAndSettle();
    expect(key('score'), findsOneWidget);
  });

  testWidgets('the real links open the lesson and the coach', (t) async {
    final links = mockRoutes(rig.s);
    await pumpScreen(
      t,
      Builder(
        builder: (c) => Scaffold(
          body: Row(
            children: [
              TextButton(
                key: const ValueKey('lesson'),
                onPressed: () => unawaited(links.openLesson(c, 'joins-null')),
                child: const Icon(Icons.school),
              ),
              TextButton(
                key: const ValueKey('coach'),
                onPressed: () => unawaited(links.openCoach(c, 'two-sum')),
                child: const Icon(Icons.psychology),
              ),
            ],
          ),
        ),
      ),
      size: phone,
    );
    await t.tap(key('lesson'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 500));
    expect(find.byType(SqlLessonScreen), findsOneWidget);
    Navigator.of(t.element(find.byType(SqlLessonScreen))).pop();
    await t.pump();
    await t.pump(const Duration(milliseconds: 500));
    await t.tap(key('coach'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 500));
    expect(find.byType(CoachScreen), findsOneWidget);
  });
}
