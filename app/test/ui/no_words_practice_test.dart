// textgate guard, practice screens: the mock test, coach, SQL drills and
// lessons, and the focus screen paint no app words in their working states
// (the entry states are in no_words_test.dart).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tutor/mock/mock_entry.dart';
import 'package:tutor/mock/mock_result_screen.dart';
import 'package:tutor/mock/mock_start_screen.dart';
import 'package:tutor/storage/kv_store.dart';
import 'package:tutor/ui/coach/coach_picker.dart';
import 'package:tutor/ui/coach/coach_postmortem.dart';
import 'package:tutor/ui/focus_screen.dart';
import 'package:tutor/ui/sql/drill_screen.dart';
import 'package:tutor/ui/sql/lesson_screen.dart';
import 'package:tutor/ui/sql/sql_screen.dart';

import '../coach/coach_fixtures.dart' as c;
import '../mock/mock_fixtures.dart';
import '../mock/mock_support.dart';
import '../sql/sql_fixtures.dart' as q;
import '../support/fake_rtdb.dart';
import '../support/fake_stream.dart';
import '../support/no_words.dart';
import '../support/services.dart';
import '../support/ui.dart';
import 'coach/coach_support.dart' show CoachRig;

const _focusProject = <String, Object>{
  'id': 'prep',
  'name': 'HackerRank prep',
  'start': '2026-11-02',
  'end': '2026-11-05',
  'days_left': 4,
  'replaces': ['leetcode'],
  'daily_minutes': 120,
  'unlock_minutes': 30,
  'subjects': ['automation'],
  'site_patterns': ['hackerrank.com'],
};

void main() {
  group('mock test', () {
    late Rig rig;
    setUp(() => rig = Rig());

    testWidgets('start screen (reached, not loading)', (t) async {
      await pumpScreen(
        t,
        MockStartScreen(services: rig.s, links: rig.links),
        size: phone,
      );
      expect(find.byType(MockStartScreen), findsOneWidget);
      expectNoWords(t, 'mock start');
    });

    testWidgets('start screen failure cue', (t) async {
      await pumpScreen(
        t,
        MockStartScreen(services: rig.s, links: rig.links),
        size: phone,
        settle: false,
      );
      await t.tap(find.byKey(const ValueKey('start')));
      await sent(t);
      await answer(t, rig.db, rig.stream, data: const {'tasks': 5});
      expectNoWords(t, 'mock start problem');
    });

    testWidgets('entry opens the start screen', (t) async {
      await pumpScreen(
        t,
        Builder(
          builder: (c) => TextButton(
            onPressed: () => unawaited(openMock(c, rig.s, links: rig.links)),
            child: const Text('x'),
          ),
        ),
        size: phone,
      );
      await t.tap(find.byType(TextButton));
      await t.pumpAndSettle();
      expect(find.byType(MockStartScreen), findsOneWidget);
    });

    testWidgets('test running: notes, chips, question, options', (t) async {
      await rig.pumpTest(t);
      expectNoWords(t, 'mock question');
      await t.tap(find.byKey(const ValueKey('opt-1')));
      await t.pumpAndSettle();
      await t.tap(find.byKey(const ValueKey('nav-3')));
      await t.pump();
      expectNoWords(t, 'mock sql task');
      await t.tap(find.byKey(const ValueKey('finish')));
      await t.pumpAndSettle();
      expectNoWords(t, 'mock finish dialog');
    });

    testWidgets('result with details', (t) async {
      final m = rig.session()..finished(resultData);
      await pumpScreen(
        t,
        MockResultScreen(services: rig.s, session: m, links: rig.links),
        size: phone,
      );
      expectNoWords(t, 'mock result');
      await t.tap(find.byKey(const ValueKey('item-q1')));
      await t.pumpAndSettle();
      expectNoWords(t, 'mock result opened');
    });
  });

  group('coach', () {
    late CoachRig rig;
    setUp(() => rig = CoachRig());

    testWidgets('chat, reply with a snippet, a failed run', (t) async {
      await rig.open(t);
      expectNoWords(t, 'coach chat');
      await rig.say(t, 'two pointers');
      await rig.reply(t, c.turnData);
      expectNoWords(t, 'coach reply');
      await rig.tap(t, 'reveal');
      expectNoWords(t, 'coach reveal dialog');
      await t.tap(find.byKey(const ValueKey('reveal-cancel')));
      await t.pumpAndSettle();
    });

    testWidgets('a failed turn is an error cue', (t) async {
      await rig.open(t);
      await rig.say(t, 'hello');
      await rig.reply(t, const {}, code: 'model_error');
      expectNoWords(t, 'coach turn failed');
    });

    testWidgets('SQL problem opens', (t) async {
      await rig.open(t, first: c.sqlOpenData);
      expectNoWords(t, 'coach sql');
    });
  });

  group('coach lists', () {
    late FakeRtdb db;
    late FakeStream stream;

    testWidgets('picker with due, recent and clusters', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        CoachPickerScreen(services: services(db, stream)),
        settle: false,
      );
      await answer(t, db, stream, data: c.listData);
      expectNoWords(t, 'coach picker');
    });

    testWidgets('post-mortem cards', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        CoachPostMortemScreen(
          services: services(db, stream),
          lcId: c.lcId,
          summaryMd: 'Two pointers.',
        ),
        settle: false,
      );
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: c.cardsData);
      expectNoWords(t, 'coach post-mortem');
    });
  });

  group('sql', () {
    late FakeRtdb db;
    late FakeStream stream;
    late MemoryKv kv;
    setUp(() => kv = MemoryKv());

    Future<void> drill(WidgetTester t, Map<String, Object?> data) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        SqlDrillScreen(
          services: services(db, stream, kv: kv),
          id: 'basics-1',
          title: 'Count rows',
        ),
        settle: false,
      );
      await answer(t, db, stream, data: data);
    }

    Future<void> run(WidgetTester t, String sql) async {
      await t.enterText(find.byKey(const ValueKey('sql-editor')), sql);
      await t.pump();
      await t.tap(find.byKey(const ValueKey('run')));
      await t.pump(const Duration(milliseconds: 50));
    }

    testWidgets('list of drills', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        SqlPracticeScreen(services: services(db, stream)),
        settle: false,
      );
      await answer(t, db, stream, data: q.listData);
      expectNoWords(t, 'sql list');
    });

    testWidgets('write drill: wrong result, hint, error', (t) async {
      await drill(t, q.writeDrillData);
      expectNoWords(t, 'sql drill');
      await run(t, 'select count(*) from emp');
      await answer(t, db, stream, data: q.runBadData);
      expectNoWords(t, 'sql drill wrong result');
      await t.tap(find.byKey(const ValueKey('hint')));
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: const {'question': 'Which rows?'});
      expectNoWords(t, 'sql drill hint');
      await run(t, 'selec');
      await answer(t, db, stream, data: const {'ok': false, 'error': 'E 1064'});
      expectNoWords(t, 'sql drill error');
    });

    testWidgets('a malformed result is an error cue', (t) async {
      await drill(t, q.writeDrillData);
      await run(t, 'select 1');
      await answer(t, db, stream, data: const {'rows': 5});
      expectNoWords(t, 'sql drill malformed');
    });

    testWidgets('predict drill', (t) async {
      await drill(t, q.predictDrillData);
      expectNoWords(t, 'sql predict');
    });

    testWidgets('lesson turn', (t) async {
      db = FakeRtdb();
      stream = FakeStream();
      await pumpScreen(
        t,
        SqlLessonScreen(
          services: services(db, stream, kv: kv),
          topic: 'basics',
        ),
        settle: false,
      );
      await t.pump(const Duration(milliseconds: 50));
      await answer(t, db, stream, data: q.lessonTurnData);
      expectNoWords(t, 'sql lesson');
    });
  });

  group('focus', () {
    for (final active in [true, false]) {
      testWidgets('focus screen (project: $active)', (t) async {
        final db = FakeRtdb();
        final stream = FakeStream();
        final s = services(db, stream, kv: MemoryKv());
        addTearDown(s.focus.dispose);
        await pumpScreen(t, FocusScreen(services: s), settle: false);
        await answer(
          t,
          db,
          stream,
          data: {
            'day': '2026-11-02',
            'active': active ? {..._focusProject, 'minutes': 42} : null,
            'projects': [_focusProject],
            'gates': [
              {'id': 'leetcode', 'label': 'LeetCode', 'replaceable': true},
              {'id': 'workout', 'label': 'Workout', 'replaceable': false},
            ],
            'subjects': [
              {'id': 'automation', 'title': 'Automation'},
            ],
          },
        );
        expectNoWords(t, 'focus (project: $active)');
      });
    }
  });
}
